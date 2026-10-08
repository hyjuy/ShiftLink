/* ShiftLink PDA — 동작하는 프로토타입 (모의 MES 서버가 /pda.html 로 서빙)
 * ─────────────────────────────────────────────────────────────────────
 * 설계: docs/planning/PDA_카메라_설비식별_고도화.md
 * 작업계획: docs/planning/PDA_라즈베리파이_모니터_작업계획_20261001.md (C4)
 * 구상: docs/design/pda_ui/pda_ui_mockup.html
 *
 * 지키는 규범
 *   C-102  검색 대상 = status=accepted AND split=kb AND grade=L1 (/api/kb/cards 가 거름)
 *   C-099  sealed 분할은 열지 않는다 — 서버가 kb 파일만 읽음
 *   D-41   확정되지 않았거나 구성에 없는 설비로는 검색하지 않는다
 *   D-42   원본 이미지는 단말 밖으로 나가지 않는다 — 분류는 라즈베리파이(shiftlink.vision.classify)가 하고
 *          화면은 /api/equipment/scan/recent 결과만 받는다 (작업계획 C6)
 *   §9.2   QueryRequest.eq_id 에는 equipment_id 를 넣는다
 *
 * MES 정렬 (2026-10-01)
 *   설비·신호·정상 범위 = /api/config (현재 run 의 구성). 기준정보 alarm_low/high 는 상태 경계로 쓰지 않는다.
 *   관측값 = /api/state. MesCardAdapter 와 같은 규칙: quality=good·단위 일치·유한 숫자(bool 은 0/1),
 *   시료는 60초 이내만. 원값과 <signal>_state(low/normal/high, 경계 포함 normal)를 조건 평가에 쓴다.
 *   카드 = card.equipment 가 설비 유형이거나 COMMON, mes_equipment_id 가 있으면 그 설치만.
 */
'use strict';

const SCAN_POLL_MS = 500;
const SCAN_TIMEOUT_MS = 20000;  // 이 안에 새 인식이 없으면 직접 선택으로
const API_TIMEOUT_MS = 8000;
const RECENT_MAX = 3;

const TYPE_COLOR = { HPU:'hpu', GR:'gr', RT:'rt', CV:'cv', PDP:'pdp', CAU:'cau' };

// ── 상태 ───────────────────────────────────────────────────────────
const S = {
  screen:'boot', equipment:[], cards:[], handovers:[], basisRecords:{}, groups:{}, types:{},
  eq:null, source:null, scanId:null,
  chat:[], chatSeq:0,   // 증상 질의 대화. 한 턴 = /api/query 한 번 — 이전 턴은 서버로 보내지 않는다
  observations:[], obsRemoved:[], recent:[], outbox:[], online:null, netNote:null,
  scanRun:0, scanStartedAt:0, mes:null, mesExcluded:[],
  waitAbort:false, ranked:null, tries:[], attemptSeq:0,
  operator:null, linkedEquipment:null
};

const $ = (id) => document.getElementById(id);
const byType = (t) => TYPE_COLOR[t] ? 'var(--' + TYPE_COLOR[t] + ')' : 'var(--tx-3)';
const findByCode = (code) => S.equipment.find((e) => e.code === code) || null;
// 스캔 결과의 code가 현재 구성에 있을 때만 그 설비. 없으면 null(대체 확정 금지, D-41).
const scanTarget = (scan, equipment) => (scan && scan.code && equipment.find((e) => e.code === scan.code)) || null;
// retrieval.py 와 같은 규칙: 유형 일치 또는 COMMON, 설치 지정 카드는 그 설치에서만.
const cardFits = (c, eq) => (c.equipment === eq.type || c.equipment === 'COMMON')
  && (!c.mes_equipment_id || c.mes_equipment_id === eq.equipment_id);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// 화면용 단위 표기(데이터의 unit 값은 그대로 둔다). MES 대시보드 operator.js 의 unitText 와 같은 표.
const UNIT_TEXT = { m_min: 'm/min', L_min: 'L/min', mm_s: 'mm/s', degC: '℃', pct: '%', bool: '', min: '분' };
const unitText = (u) => (u in UNIT_TEXT ? UNIT_TEXT[u] : String(u || '').replace(/_/g, '/'));
/* 신호 ID 대신 MES 구성의 한글 이름. 파생 <signal>_state 는 "이름 상태". */
function signalName(sig) {
  const base = String(sig).replace(/_state$/, '');
  const spec = S.eq && S.eq.signals.find((x) => x.signal === base);
  const name = spec ? String(spec.name || base).split(' (')[0] : base;
  return base !== sig ? name + ' 상태' : name;
}
const obsText = (o) => signalName(o.signal) + ' ' + o.value + (unitText(o.unit) ? ' ' + unitText(o.unit) : '');


// ── 부팅: MES 구성·카드 적재 ───────────────────────────────────────
async function getJson(path) {
  const res = await api(path);
  if (!res.ok) throw new Error(path + ' — HTTP ' + res.status);
  return res.json();
}

/* Unity FactoryRig.Layout과 같은 좌표. 구성의 route 순서로 주 이송로 위치를 계산한다. */
function unityLocation(eq, config, auxiliary) {
  const route = config.route || [];
  const index = route.indexOf(eq.equipment_id), count = route.length;
  let x, y = 0, z, area;
  if (index >= 0) {
    x = (index - (count - 1) * .5) * 5.4; z = 0;
    area = '주 이송로 ' + (index + 1) + '번째';
  } else {
    const positions = {'GR-01':[-(count-1)*2.7-3.8,0,3], 'GR-02':[(count-3)*2.7-3.8,0,3],
      'HPU-01':[-6,0,8], 'PDP-01':[-2,0,8], 'CAU-01':[3,3.2,8], 'CV-02':[(count-3)*2.7+1.7,0,-4]};
    [x,y,z] = positions[eq.code] || [auxiliary*3,0,9];
    area = String(eq.code || '').startsWith('GR-') ? '이송로 구동부' : eq.code === 'CV-02' ? '분기 이송로' : '보조 설비 구역';
  }
  return 'Unity 가상 공장 · ' + area + ' (X ' + Number(x.toFixed(1)) + ', Y ' + y + ', Z ' + z + ')';
}

/* MES 구성의 설비·신호에 기준정보의 그룹명·위치 문구만 덧붙인다. */
function equipmentFrom(config, catalog) {
  const groups = {}, rows = {};
  (catalog.equipment_groups || []).forEach((g) => { groups[g.equipment_group_id] = g; });
  (catalog.equipment || []).forEach((e) => { rows[e.equipment_id] = e; });
  return (config.equipment || []).filter((e) => e.active !== false).map((e) => {
    const row = rows[e.equipment_id] || {};
    return {
      equipment_id: e.equipment_id,
      code: e.code,
      type: String(e.code).split('-')[0],
      group: (groups[row.equipment_group_id] || {}).name || e.name || '',
      where: unityLocation(e, config, config.equipment.indexOf(e)),
      signals: (e.signals || []).map((m) => ({
        signal: m.signal, name: m.name || m.signal, unit: m.unit,
        min: m.normal_min, max: m.normal_max, semantics: m.semantics || {}, zeroStopped: m.zero_when_stopped === true
      }))
    };
  });
}

function equipmentFromLink(search, equipment) {
  const params = new URLSearchParams(search);
  const ids = params.getAll('equipment_id');
  if (ids.length !== 1) return null;
  return equipment.find((eq) => eq.equipment_id === ids[0]) || null;
}

let afterBoot = () => show('login');   // 문서 블록이 로그인 기억(sessionStorage)으로 바꾼다

async function boot() {
  $('bootErr').innerHTML = '';
  try {
    const [cfg, cat, kb] = await Promise.all([getJson('/api/config'), getJson('/api/catalog'), getJson('/api/kb/cards')]);
    S.equipment = equipmentFrom(cfg.config, cat.data);
    S.cards = kb.cards || [];
    S.handovers = kb.handovers || [];
    S.basisRecords = kb.basis_records || {};

    if (!S.equipment.length || !S.cards.length) throw new Error('구성 또는 카드가 비어 있습니다');

    renderManualList();
    S.linkedEquipment = equipmentFromLink(window.location.search, S.equipment);
    afterBoot();
  } catch (err) {
    $('bootMsg').textContent = 'MES 연결을 기다리고 있습니다. 3초 후 다시 시도합니다.';
    const box = document.createElement('div');
    box.className = 'alert bad';
    box.innerHTML = '<p class="hd">데이터 로드 실패</p><p class="p"></p>'
      + '<p class="p">MES 연결이 복구되면 자동으로 시작합니다.</p>';
    box.querySelector('.p').textContent = String(err && err.message || err);
    $('bootErr').appendChild(box);
    setTimeout(boot, 3000);
  }
}

// ── 화면 전환 ──────────────────────────────────────────────────────
let faceStream = null;
// 블록 밖(최상위)에 둔다: stopFaceCamera·show가 최상위 함수라 브라우저 블록 안 선언은 보이지 않는다(10/7 ReferenceError).
let faceRun = 0;

function stopFaceCamera() {
  faceRun += 1;
  if (faceStream) {
    faceStream.getTracks().forEach((track) => track.stop());
    faceStream = null;
  }
  if (typeof document !== 'undefined') {
    const video = document.getElementById('faceVideo');
    if (video) video.srcObject = null;
  }
}

function show(name) {
  if (S.screen === 'scan' && name !== 'scan') S.scanRun += 1;  // 폴링 중단
  if (S.screen === 'face' && name !== 'face') stopFaceCamera();
  S.screen = name;
  document.querySelectorAll('.screen').forEach((el) => {
    el.classList.toggle('on', el.id === 's-' + name);
  });
  const hideCtx = name === 'scan' || name === 'manual' || name === 'boot' || name === 'alertGo'
    || name === 'login' || name === 'face';
  $('ctx').classList.toggle('on', !!S.eq && !hideCtx);
  $('net').hidden = (name === 'boot');
  const pane = document.querySelector('#s-' + name + ' .pane');
  if (pane) pane.scrollTop = 0;
  document.documentElement.scrollTop = 0;
  document.body.scrollTop = 0;
  if (name === 'chat') { renderMesStatus(); renderChat(); }
}

function haptic(p) { if (navigator.vibrate) { try { navigator.vibrate(p); } catch (_) {} } }

// ── 네트워크 ───────────────────────────────────────────────────────
function renderNet() {
  const el = $('net');
  el.classList.toggle('ok', S.online === true);
  el.classList.toggle('warn', S.online === false);
  $('netText').textContent =
    S.online === true ? '로컬 정상' :
    S.online === false ? (S.netNote || 'Jetson에 연결할 수 없음') : '연결 확인 중…';
  const q = $('netQueue');
  q.hidden = S.outbox.length === 0;
  q.textContent = '대기 ' + S.outbox.length + '건';
}

async function api(path, init, timeoutMs = API_TIMEOUT_MS) {
  const ctrl = new AbortController();
  const to = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(path, Object.assign({ signal: ctrl.signal, cache: 'no-store' }, init));
    S.online = res.ok;
    S.netNote = res.ok ? null : 'MES 아님 (HTTP ' + res.status + ')';
    renderNet();
    return res;
  } catch (err) {
    S.online = false; S.netNote = null; renderNet(); throw err;
  } finally { clearTimeout(to); }
}

async function probeServer() { try { await api('/api/state'); } catch (_) {} }

// ── 컨텍스트 ───────────────────────────────────────────────────────
function setContext(eq, source, extra) {
  S.eq = eq; S.source = source; S.queryResponse = null;
  S.scanId = (extra && extra.scanId) || null;
  S.observations = []; S.obsRemoved = []; S.ranked = null; S.tries = []; S.attemptSeq = 0; S.chat = [];
  S.safetyView = null;
  S.mes = null; S.mesExcluded = [];
  S.recent = [eq.code].concat(S.recent.filter((c) => c !== eq.code)).slice(0, RECENT_MAX);
  renderContext(); renderRecent(); renderObsSignals(); renderObsList(); renderMesStatus();
  loadMesObservations();
}

/* 확정 설비 해제. 이전 설비의 관측·응답·시도도 함께 버린다. */
function releaseContext(state) {
  Object.assign(state, {eq: null, source: null, scanId: null, queryResponse: null, ranked: null,
    observations: [], obsRemoved: [], mes: null, mesExcluded: [], tries: [], attemptSeq: 0, chat: []});
}

function renderContext() {
  if (!S.eq) { $('ctx').classList.remove('on'); return; }
  $('ctxRail').style.background = byType(S.eq.type);
  $('ctxId').textContent = S.eq.code;
  $('ctxName').textContent = S.eq.group;
  $('ctxFoot').textContent = S.eq.equipment_id + ' · ' + S.eq.where;
}

function renderRecent() {
  const box = $('recent'); box.innerHTML = '';
  if (!S.recent.length) { box.innerHTML = '<p class="hint">아직 없습니다.</p>'; return; }
  S.recent.forEach((code) => {
    const eq = findByCode(code); if (!eq) return;
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'chip';
    b.innerHTML = '<i class="sw"></i>' + eq.code;
    b.querySelector('.sw').style.background = byType(eq.type);
    // 스캔을 우회한 진입이므로 출처는 manual_selection 으로 남긴다(§6.2).
    b.addEventListener('click', () => { setContext(eq, 'manual_selection', {}); show('ctx'); });
    box.appendChild(b);
  });
}

// ── 스캔 ───────────────────────────────────────────────────────────
function setScanState(kind, text) {
  $('reticle').className = 'reticle' + (kind ? ' ' + kind : '');
  $('scanState').className = kind || '';
  $('scanText').textContent = text;
}

async function latestScan() {
  return (await getJson('/api/equipment/scan/recent?limit=1')).scans[0] || null;
}

/* 라즈베리파이가 확정해 Jetson에 올린 인식 결과를 폴링한다. 시작 시점의 최신 scan_id 보다 새 것만 받는다
 * (파이·Jetson 시계를 비교하지 않으려고). 파이는 같은 객체를 한 번만 보내므로 이미 놓여 있던 상자는
 * 치웠다가 다시 놓아야 잡힌다. */
async function startScan() {
  const run = ++S.scanRun;
  show('scan'); setScanState('', 'Jetson 연결 확인 중…');
  let base;
  try { base = await latestScan(); } catch (_) { return failScan(run, 'Jetson에 연결할 수 없음 — 직접 선택'); }
  if (S.scanRun !== run) return;
  S.scanStartedAt = Date.now();
  setScanState('', '웹캠 앞에 상자를 놓으세요');
  while (Date.now() - S.scanStartedAt < SCAN_TIMEOUT_MS) {
    await sleep(SCAN_POLL_MS);
    if (S.scanRun !== run) return;
    let scan = null;
    try { scan = await latestScan(); } catch (_) { continue; }
    if (S.scanRun !== run) return;
    if (!scan || (base && scan.scan_id === base.scan_id)) continue;
    base = scan;
    // D-41: 현재 구성에 있는 code만 확정한다. 같은 유형의 다른 설비로 바꿔 끼우지 않는다 —
    // 질의는 scan_id로 나가므로 화면의 설비와 서버가 푸는 설비가 갈라진다.
    const eq = scanTarget(scan, S.equipment);
    if (!eq) {
      // 화면이 「설비 미확정」이면 상태도 미확정이어야 한다 — 「← 이전」으로 직전 설비 검색에 돌아가지 않게(B3).
      releaseContext(S); renderContext();
      setScanState('failed', (scan.code || scan.class || '알 수 없는 설비') + ' — 현재 구성에 없는 설비 code · 검색 불가'); continue;
    }
    return lockScan(eq, scan);
  }
  if (S.scanRun === run) failScan(run, '인식 안 됨 — 직접 선택');
}

function lockScan(eq, scan) {
  haptic([120]);
  setScanState('locked', eq.code + ' 확정');
  setContext(eq, 'camera_scan', { scanId: scan.scan_id });
  setTimeout(() => { if (S.screen === 'scan') show('ctx'); }, 420);
}

/* 시간 초과·Jetson 연결 실패. 직접 선택 화면은 「설비 미확정」이므로 상태도 해제한다 —
 * 「← 이전」으로 직전 설비 검색에 돌아가지 않게(B3, 구성 외 code 경로와 같은 처리). */
function failScan(run, text) {
  releaseContext(S); renderContext();
  haptic([30, 60, 30]);
  setScanState('failed', text);
  setTimeout(() => { if (S.screen === 'scan' && S.scanRun === run) openManual(); }, 900);
}

// ── 직접 선택 ──────────────────────────────────────────────────────
function renderManualList() {
  const list = $('manualList'); list.innerHTML = '';
  S.equipment.forEach((eq) => {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'row';
    b.innerHTML = '<i class="rail"></i><span class="txt"><span class="id"></span><br>'
      + '<span class="nm"></span></span>';
    b.querySelector('.rail').style.background = byType(eq.type);
    b.querySelector('.id').textContent = eq.code;
    b.querySelector('.nm').textContent = eq.group + ' · ' + eq.where;
    b.addEventListener('click', () => {
      setContext(eq, 'manual_selection', {}); haptic(30); show('ctx');
    });
    list.appendChild(b);
  });
}
function openManual() { show('manual'); }

// ── 관측값 ─────────────────────────────────────────────────────────
function renderObsSignals() {
  const sel = $('obsSignal'); sel.innerHTML = '';
  if (!S.eq) return;
  S.eq.signals.forEach((s) => {
    const o = document.createElement('option');
    o.value = s.signal; o.textContent = String(s.name).split(' (')[0] + (unitText(s.unit) ? ' (' + unitText(s.unit) + ')' : '');
    sel.appendChild(o);
  });
  renderObsRange();
}
function renderObsRange() {
  const s = (S.eq && S.eq.signals.find((x) => x.signal === $('obsSignal').value)) || null;
  $('obsRange').textContent = s ? '정상 범위 ' + fmt(s.min) + '~' + fmt(s.max) + ' ' + unitText(s.unit) + ' (MES 구성값)' : '';
}
const fmt = (v) => (v == null ? '—' : String(v));
const num = (v) => String(Number(Number(v).toFixed(3)));
const stamp = (v) => (v ? new Date(v).toLocaleTimeString('ko-KR', { hour12: false }) : '시각 없음');

/* MesCardAdapter 와 같은 판정. 경계값은 normal. 범위가 없으면 상태 없음. */
function stateOf(spec, value) {
  if (!spec || (spec.min == null && spec.max == null)) return null;
  if (spec.min != null && value < spec.min) return 'low';
  if (spec.max != null && value > spec.max) return 'high';
  return 'normal';
}

/* 현재 MES 관측 중 조건 평가에 쓸 수 있는 값만 고른다(MesCardAdapter 규칙). */
function usableReadings(snap, eq) {
  const specs = {};
  eq.signals.forEach((x) => { specs[x.signal] = x; });
  const frame = Date.parse(snap.simulated_at);
  const kept = [], excluded = [];
  (snap.measurements || []).forEach((m) => {
    const spec = specs[m.signal];
    if (m.equipment_id !== eq.equipment_id || !spec) return;
    const v = m.value;
    let ok = m.quality === 'good' && m.unit === spec.unit && typeof v === 'number' && Number.isFinite(v)
      && (spec.unit !== 'bool' || v === 0 || v === 1);
    if (ok && spec.semantics.acquisition === 'manual_sample') {
      const age = (frame - Date.parse(m.observed_at)) / 1000;
      ok = age >= 0 && age < 60;
    }
    if (ok) kept.push({ signal: m.signal, value: v, unit: spec.unit, source: 'mes', observed_at: m.observed_at });
    else excluded.push(m.signal);
  });
  return { kept: kept, excluded: excluded };
}

/* 선택 설비의 현재 MES 관측으로 채운다. 직접 입력한 값은 덮어쓰지 않는다. */
async function loadMesObservations(given) {
  const eq = S.eq;
  if (!eq) return;
  let snap = given;
  if (!snap) {
    try { snap = await getJson('/api/state'); } catch (_) { if (S.eq === eq) clearMesObservations(); return; }
  }
  if (S.eq !== eq) return;
  const r = usableReadings(snap, eq);
  const manual = S.observations.filter((o) => o.source === 'manual');
  // 실시간 갱신이 작업자가 ✕로 뺀 MES 값을 되살리지 않게 한다.
  S.observations = manual.concat(r.kept.filter((o) => !manual.some((x) => x.signal === o.signal)
    && !S.obsRemoved.includes(o.signal)));
  S.mesExcluded = r.excluded;
  const state = (snap.equipment || []).find((e) => e.equipment_id === eq.equipment_id) || {};
  S.mes = {
    readings: r.kept,
    at: snap.simulated_at, operating: state.operating_state, fault: state.fault_level,
    alarms: (snap.active_alarms || []).filter((a) => a.equipment_id === eq.equipment_id).map((a) => a.label || a.code),
    diagnoses: (snap.symptom_diagnostics || []).filter((d) => d.equipment_id === eq.equipment_id)
  };
  renderObsList(); renderMesStatus();
  // 증상 순서는 관측에 따라 바뀐다. 순서가 달라졌을 때만 다시 그린다(목록 깜박임 방지).
  if (S.screen === 'chat' && symKey(symptomsFor(eq)) !== S.symKey) renderSymptoms();
}

function clearMesObservations() {
  S.mes = null;
  S.observations = S.observations.filter((o) => o.source === 'manual');
  S.mesExcluded = [];
  renderObsList(); renderMesStatus();
  if (S.screen === 'chat') renderSymptoms();
}

function readingDetail(o, spec) {
  return '정상 범위 ' + fmt(spec.min) + '~' + fmt(spec.max) + ' ' + unitText(spec.unit)
    + (o.observed_at ? ' · 측정 ' + stamp(o.observed_at) : '');
}

/* 현재 센서와 답변의 고정 근거를 같은 표기로 표시한다. 질의 입력의 수동 덮어쓰기는 별도로 유지한다. */
function renderSensorReadings(box, readings, operating) {
  readings.forEach((o) => {
    const spec = S.eq.signals.find((s) => s.signal === o.signal);
    if (!spec) return;
    const row = document.createElement('div');
    const stopped = spec.zeroStopped && o.value === 0 && operating && operating !== 'running';
    const status = stopped ? 'stopped' : stateOf(spec, o.value);
    row.className = 'obs' + (status === 'low' || status === 'high' ? ' out' : '');
    row.innerHTML = '<span class="txt"><span class="mono"></span><small></small></span>';
    row.querySelector('.mono').textContent = obsText(o);
    row.querySelector('small').textContent = readingDetail(o, spec) + ' · ' + (stopped ? '정지 중 0' : stateWord(status) || '범위 미설정');
    box.appendChild(row);
  });
}

/* 범위 이탈이면 방향과 경계 대비 차이를 만든다. MES 운영 화면과 같은 표기. */
function obsView(o) {
  const spec = S.eq.signals.find((x) => x.signal === o.signal);
  // MES 운영 화면과 같이 정지 중 0 은 이탈로 강조하지 않는다. 카드 조건 판정(stateOf)은 어댑터 규칙 그대로.
  if (spec && spec.zeroStopped && o.value === 0 && S.mes && S.mes.operating !== 'running') return { st: 'stopped', text: '' };
  const st = stateOf(spec, o.value);
  if (st !== 'low' && st !== 'high') return { st: st, text: '' };
  const bound = st === 'low' ? spec.min : spec.max, diff = o.value - bound;
  const pct = bound ? ' (' + (diff > 0 ? '+' : '') + Math.round(diff / Math.abs(bound) * 100) + '%)' : '';
  return { st: st, text: (st === 'low' ? '▼ 하한 ' : '▲ 상한 ') + num(bound) + ' 대비 '
    + (diff > 0 ? '+' : '') + num(diff) + ' ' + unitText(o.unit) + pct };
}

function renderObsList() {
  const box = $('obsList'); box.innerHTML = '';
  if (!S.eq) return;
  const rows = S.observations.map((o) => ({ o: o, v: obsView(o) }));
  const out = rows.filter((r) => r.v.text);
  const head = document.createElement('p');
  head.className = 'hint';
  head.textContent = S.mes
    ? 'MES 관측 ' + S.observations.filter((o) => o.source === 'mes').length + '개 · 범위 이탈 ' + out.length + '개'
      + (S.mesExcluded.length ? ' · 품질·시각 미충족 제외 ' + S.mesExcluded.length + '개' : '') + ' · ' + stamp(S.mes.at)
    : 'MES 관측을 읽지 못했습니다. 직접 추가한 값만 사용합니다.';
  box.appendChild(head);
  const mk = (r) => {
    const row = document.createElement('div');
    row.className = 'obs' + (r.v.text ? ' out' : '');
    row.innerHTML = '<span class="txt"><span class="mono"></span><small></small></span>'
      + '<button class="x" type="button" aria-label="삭제">✕</button>';
    const spec = S.eq.signals.find((x) => x.signal === r.o.signal) || {};
    row.querySelector('.mono').textContent = signalName(r.o.signal) + ' = ' + r.o.value + (unitText(r.o.unit) ? ' ' + unitText(r.o.unit) : '');
    row.querySelector('small').textContent = (r.v.text ? r.v.text + ' · ' : r.v.st === 'stopped' ? '정지 중 0 · 정상 · ' : '')
      + (r.o.source === 'manual' ? '직접 입력' : 'MES') + ' · ' + readingDetail(r.o, spec);
    row.querySelector('.x').addEventListener('click', () => {
      S.observations.splice(S.observations.indexOf(r.o), 1);
      if (r.o.source === 'mes') S.obsRemoved.push(r.o.signal);
      renderObsList();
    });
    return row;
  };
  // 범위 이탈을 먼저 보이고, 이탈이 있으면 나머지는 접는다.
  out.forEach((r) => box.appendChild(mk(r)));
  const rest = rows.filter((r) => !r.v.text);
  if (!rest.length) return;
  if (!out.length) { rest.forEach((r) => box.appendChild(mk(r))); return; }
  const d = document.createElement('details');
  d.innerHTML = '<summary class="hint">나머지 ' + rest.length + '개 보기 · 범위 내·정지 중 0·판정 불가</summary>';
  rest.forEach((r) => d.appendChild(mk(r)));
  box.appendChild(d);
}

const STATE_TXT = { running:'가동', stopped:'정지', waiting:'대기', normal:'정상', warning:'주의', critical:'자체 이상' };

function renderMesStatus() {
  const box = $('ctxMes');
  const sensors = $('ctxSensors'); sensors.innerHTML = '';
  if (S.mes) {
    renderSensorReadings(sensors, S.mes.readings || [], S.mes.operating);
    if (!(S.mes.readings || []).length) sensors.textContent = '사용 가능한 센서값이 없습니다.';
  } else sensors.textContent = 'MES 연결을 확인해 주세요. 현재 센서값을 읽지 못했습니다.';
  const chat = $('chatMes');
  const out = S.observations.filter((o) => obsView(o).text).length;
  $('obsSummary').textContent = '관측값 · 직접 입력 — 범위 이탈 ' + out + '개';
  if (S.screen === 'chat') renderAskSafety();
  if (!S.mes) {
    box.textContent = 'MES 상태를 읽지 못했습니다.'; box.classList.remove('bad');
    chat.textContent = (S.eq ? S.eq.code + ' · ' : '') + 'MES 상태를 읽지 못했습니다.'; chat.classList.toggle('bad', true);
    return;
  }
  const parts = ['MES ' + (STATE_TXT[S.mes.operating] || S.mes.operating || '—') + ' · '
    + (STATE_TXT[S.mes.fault] || S.mes.fault || '—')];
  if (S.mes.alarms.length) parts.push('경보 ' + S.mes.alarms.join(', '));
  parts.push('범위 이탈 ' + out + '개');
  S.mes.diagnoses.forEach((d) => parts.push('증상 후보: ' + d.symptom + ' (확정 아님)'));
  box.textContent = parts.join(' · ');
  const bad = out > 0 || (!!S.mes.fault && S.mes.fault !== 'normal');
  box.classList.toggle('bad', bad);
  chat.textContent = (S.eq ? S.eq.code + ' ' + (S.eq.group || '') + ' · ' : '') + parts.join(' · ');
  chat.classList.toggle('bad', bad || S.mes.alarms.length > 0);
}

/* 안전 수칙을 관문 색으로 펼칠 때 — MES를 못 읽음·정지·대기·이상·경보·증상 후보·범위 이탈, 또는 안전 카드의
 * 조건이 지금 관측과 맞을 때. 그 밖(정상 가동)에는 접는다. 답 말풍선의 안전 카드는 이 규칙과 무관하게 항상 답 앞(G2). */
function safetyAlert(mes, observations, safety) {
  if (!mes) return true;
  if (mes.operating !== 'running' || (mes.fault && mes.fault !== 'normal')) return true;
  if ((mes.alarms || []).length || (mes.diagnoses || []).length) return true;
  if (observations.some((o) => { const st = obsView(o).st; return st === 'low' || st === 'high'; })) return true;
  // '정상일 때' 조건은 이상 신호가 아니다(relevance 와 같은 규칙).
  return safety.some((c) => (c.conditions || []).some((cond) => cond.value !== 'normal'
    && evalCondition(cond, observations).state === 'match'));
}

// ── 증상 선택 ──────────────────────────────────────────────────────
/* 목록은 해당 설비 카드의 `symptom` 필드에서 나온다. 지어내지 않는다.
 * 「기타」를 목록 항목과 같은 크기·같은 자리에 두는 이유 — 목록에서만 고를 수
 * 있으면 항상 무언가 찾히고 「해당 지식 없음」이 영영 나오지 않는다. 그 화면은
 * 이 시스템에서 실패가 아니라 기능이므로 도달 경로를 좁히면 안 된다. */
/* 화면 표시 이름. 질의에는 원문 symptom 을 그대로 보낸다 — 짧은 이름은 단어 겹침 검색에서
 * 0건이 나올 수 있다(10/6 시험). 'sym' 증상 · 'pre' 작업 전 확인. 없는 카드는 원문을 보인다.
 * 근거·검토: docs/design/pda_ui/symptom_labels_20261006.md */
const SYMPTOM_LABELS = {
  // HPU
  'K-1001': ['펌프 출구 압력 표시 없음', 'sym'],
  'K-1002': ['냉각기 출구 유온 58℃ 초과', 'sym'],
  'K-1004': ['소음 + 유량·압력 저하 + 거품', 'sym'],
  'K-1005': ['축압기 기능 저하 의심', 'sym'],
  'K-1008': ['작동유 우유빛 변색·젤라틴 덩어리', 'sym'],
  // CV
  'K-1011': ['아이들러 회전 80% 미만 + 마찰음', 'sym'],
  'K-1013': ['벨트 특정 구간만 편주', 'sym'],
  'K-1016': ['벨트 커버 점·줄무늬 부풂', 'sym'],
  // GR
  'K-1026': ['감속기 규칙적 이상음', 'sym'],
  'K-1027': ['감속기 누유', 'sym'],
  'K-1030': ['장착부 주변 이상음', 'sym'],
  // HPU
  'K-1201': ['차압 1.2 bar 초과 · 막힘 표시', 'sym'],
  'K-1202': ['차압 1.2 bar 초과 · 교체 판단', 'sym'],
  'K-1203': ['출구 압력 정상 · 압력/유량 부족', 'sym'],
  // CAU
  'K-1301': ['공기 압력 저하 · 공구 출력 저하', 'sym'],
  'K-1303': ['계통 압력 저하 · 누설 의심', 'sym'],
  // PDP
  'K-1307': ['모터 기동 시 버스 전압 순간 강하', 'sym'],
  // CAU
  'K-1311': ['부하 운전 중 압축기 정지', 'sym'],
  // CAU
  'K-1322': ['정전 후 압축기 기동 불가', 'sym'],
  'K-1323': ['타사 오일 · 토출 고온·소비 증가', 'sym'],
  // PDP
  'K-1324': ['정전 복구 후 차단기 투입 순서', 'pre'],
};

/* 현재 MES 상황(범위 이탈 신호)과 카드의 관련도로 선택지 순서를 정한다.
 * ponytail: 신호명 → 한글 낱말 표와 단어 포함 여부만 보는 단순 점수. 카드 문장에 그 낱말이 없으면
 * 못 올린다 — 순서 정확도가 문제가 되면 Jetson 검색 순위(/api/query 와 같은 검색)로 바꾼다. */
const SIGNAL_WORDS = [
  [/pressure|press/, ['압력']], [/temp/, ['온도', '유온', '과열', '발열']], [/_dp$/, ['차압']],
  [/flow/, ['유량', '공급량', '토출량']], [/current/, ['전류', '과부하']], [/vib/, ['진동']],
  [/speed|rpm/, ['속도', '저속', '회전']], [/tension/, ['장력', '미끄럼']], [/queue/, ['적체']],
  [/voltage/, ['전압']], [/trip/, ['트립']], [/oil_level/, ['유면']], [/oil_leak/, ['누유', '샌다']],
  [/lift/, ['승강', '리프트']], [/idler/, ['아이들러']], [/viscosity/, ['점도', '냉간', '저온']]
];
const DIR_WORDS = { low: ['저하', '부족', '낮', '없', '강하', '불가', '저속'],
  high: ['상승', '초과', '높', '고온', '과열', '증가', '적체', '트립'] };

/* 범위를 벗어난 관측 신호. 정지 중 0 은 이탈로 보지 않는다(obsView 와 같은 규칙). */
function situation() {
  if (!S.eq) return [];
  return S.observations.map((o) => ({ o: o, st: obsView(o).st })).filter((r) => r.st === 'low' || r.st === 'high')
    .map((r) => {
      const spec = S.eq.signals.find((x) => x.signal === r.o.signal) || {};
      return { signal: r.o.signal, name: String(spec.name || r.o.signal).split(' (')[0], dir: r.st };
    });
}

function relevance(c, sit) {
  const text = c.symptom || '';   // 제목은 결론 문장이라 엇방향 낱말이 섞인다(냉간 기동 카드의 '유온')
  let score = 0;
  const why = [];
  sit.forEach((s) => {
    const words = [].concat(...SIGNAL_WORDS.filter(([re]) => re.test(s.signal)).map(([, w]) => w));
    if (!text.includes(s.signal) && !words.some((w) => text.includes(w))) return;
    score += 2;
    if (DIR_WORDS[s.dir].some((w) => text.includes(w))) score += 1;
    why.push(s.name + (s.dir === 'low' ? ' ▼' : ' ▲'));
  });
  (c.conditions || []).forEach((cond) => {
    const base = S.observations.find((o) => o.signal === cond.signal.replace(/_state$/, ''));
    if (base && obsView(base).st === 'stopped') return;   // 정지 중 0 — 미평가로 둔다
    const r = evalCondition(cond);
    // '정상일 때' 조건은 이상 상황의 근거가 아니다 — 일치해도 올리지 않고, 어긋나면 내린다.
    if (r.state === 'match' && cond.value !== 'normal') { score += 3; why.push('카드 조건 일치'); }
    if (r.state === 'miss') score -= 3;
  });
  return { score: score, why: why };
}

// 순서·점수와 이상 신호가 같으면 다시 그리지 않는다(목록 깜박임 방지).
/* 고장 알림 순서: 선택 설비 → 심각도(0 경보·자체 이상, 1 경보·주의, 2 범위 이탈만) → 먼저 난 경보 → MES 등록 순서(입력 순서). */
function alertOrder(faults, selected) {
  return faults.map((f, i) => Object.assign({ i: i }, f)).sort((a, b) =>
    (b.eq === selected) - (a.eq === selected) || a.level - b.level
    || (a.at && b.at ? a.at.localeCompare(b.at) : (b.at ? 1 : 0) - (a.at ? 1 : 0)) || a.i - b.i);
}

const symKey = (items) => items.map((i) => i.text + i.score).join('|')
  + '#' + situation().map((x) => x.signal + x.dir).join('|');

function symptomsFor(eq) {
  const out = [];
  const sit = situation();
  S.cards.forEach((c) => {
    // T4 인계 카드는 증상 질의 검색에서 빠진다(retrieval.py, 10/1 회의) — 선택지에도 두지 않는다.
    // safety_flag 카드는 유형(T5·T6·T2…)과 무관하게 고르는 항목이 아니다 — 질의·대기·결과 화면의
    // 안전 관문(rankCards().safety)으로만 보인다(B4, D-26). T5는 모두 safety_flag=true라 따로 보지 않는다.
    if (!cardFits(c, eq) || c.tacit_type === 'T4' || c.safety_flag === true) return;
    const text = (c.symptom || '').trim();
    if (!text || out.some((o) => o.text === text)) return;
    const [label, group] = SYMPTOM_LABELS[c.card_id] || [text, 'sym'];
    out.push(Object.assign({ text, label, group }, relevance(c, sit)));
  });
  return out.sort((a, b) => b.score - a.score);   // 안정 정렬: 같은 점수는 카드 순서 유지
}

/* 입력칸의 질문. 계약(QueryRequest.question)은 그대로 문자열 하나다. */
function currentQuestion() {
  return $('question').value.trim();
}

/* 추천 질문 칩. 이 설비 카드의 `symptom` 원문을 보내고 화면에는 짧은 이름을 보인다. 지어내지 않는다.
 * 입력칸이 늘 열려 있으므로 목록 밖 질문도 보낼 수 있다 — 「해당 지식 없음」에 닿는 길을 좁히지 않는다. */
function renderSymptoms() {
  const list = $('symptomList');
  list.innerHTML = '';
  if (!S.eq) return;
  const items = symptomsFor(S.eq);
  S.symKey = symKey(items);
  const related = items.filter((i) => i.score > 0);
  const sit = situation();
  // 이상은 감지됐지만 그 신호를 다루는 증상 카드가 없다 — 순서가 그대로인 이유를 알린다.
  const note = $('symptomNote');
  note.hidden = !(sit.length && !related.length) && items.length > 0;
  note.textContent = !items.length ? '이 설비에 등록된 추천 질문이 없습니다. 직접 적어 보내세요.'
    : '맞는 증상 카드 없음 · ' + sit.map((x) => x.name + ' ' + (x.dir === 'low' ? '낮음' : '높음')).join(' · ') + ' — 직접 적어 보내세요';
  const pending = chatPending();
  items.forEach((item) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = item.score > 0 ? 'hot' : '';
    b.textContent = (item.score > 0 ? '▲ ' : '') + item.label;
    b.title = item.text + (item.score > 0 ? ' · MES ' + item.why.join(' · ') : '');
    b.disabled = pending;
    b.addEventListener('click', () => { haptic(20); sendChat(item.text, item.label); });
    list.appendChild(b);
  });
}

// ── 조건 평가 ──────────────────────────────────────────────────────
function cmp(op, a, b) {
  switch (op) {
    case '>=': return a >= b; case '>': return a > b;
    case '<=': return a <= b; case '<': return a < b;
    case '==': return a === b; case '!=': return a !== b;
    default: return null;
  }
}
const OPTXT = { '==':'=', '!=':'≠', '>':'>', '>=':'≥', '<':'<', '<=':'≤' };
const stateWord = (v) => ({ low: '낮음', high: '높음', normal: '정상' }[v] || v);

/* 원신호와 파생 <signal>_state 를 같은 규칙으로 찾는다. 단위가 다르면 미평가. */
function observed(c, observations = S.observations) {
  const direct = observations.find((o) => o.signal === c.signal);
  if (direct) return c.unit && direct.unit !== c.unit ? null : direct.value;
  if (!/_state$/.test(c.signal)) return null;
  const base = observations.find((o) => o.signal === c.signal.slice(0, -6));
  return base ? stateOf(S.eq.signals.find((x) => x.signal === base.signal), base.value) : null;
}

/* 관측값이 없으면 "일치"로 속이지 않고 미평가로 남긴다. */
function evalCondition(c, observations = S.observations) {
  const v = observed(c, observations);
  if (v == null) return { state:'unknown', text: signalName(c.signal) + ' — 관측값 없음' };
  const ok = cmp(c.op, v, c.value);
  if (ok === null) return { state:'unknown', text: c.signal + ' — 연산자 ' + c.op };
  return { state: ok ? 'match' : 'miss', text: signalName(c.signal) + ' ' + stateWord(v) + ' ' + (OPTXT[c.op] || c.op) + ' ' + stateWord(c.value) + ' · ' + (ok ? '일치' : '불일치') };
}

// ── 검색과 순위 산정 ───────────────────────────────────────────────
/* 실제 구현에서 이 몸통은 Jetson 왕복으로 대체된다(분리형). */
function queryPayload() {
  return {
    question: currentQuestion(),
    line_id: 'LN-0001',
    eq_id: S.eq.equipment_id,        // §9.2 — code 가 아니라 equipment_id
    eq_id_source: S.source,
    scan_id: S.scanId,
    observations: S.observations,
    k: 5
  };
}

function queryApiPayload(question, state) {
  return state.source === 'camera_scan'
    ? {question: question, scan_id: state.scanId}
    : {question: question, equipment_id: state.eq.equipment_id};
}

/* local = rankCards(eq). 서버 인용 카드에 로컬 조건 판정(일치·불일치·미평가 pill과 이유)을 card_id로 붙인다(C1·C2).
 * 로컬 판정이 없는 카드는 이유를 지어내지 않는다. 서버 unverified 는 미평가이지 불일치가 아니다.
 * 로컬에서 실제 불일치로 판정된 인용 카드만 불일치로 내린다 — 숨기지 않고 제외 목록에 남긴다. */
/* eq를 넘기면 공지·인용 안전 카드를 cardFits로 현재 설비와 대조한다. 맞지 않으면 지침 대신 불일치 경고만 남긴다(B1). */
function responseCards(response, cards, local, eq) {
  const byId = (id) => cards.find((c) => c.card_id === id);
  const mismatch = (c) => !!eq && !cardFits(c, eq);
  // 다른 설비의 안전 공지는 버리지 않되 본문·멈춤 조건은 싣지 않는다 — 엉뚱한 설비 지침이 실행되지 않게.
  const wrongEq = (id) => ({card_id: id, mismatch: true, eqCode: eq.code, stop_conditions: []});
  const judged = local ? local.actions.concat(local.excluded) : [];
  const item = (id, unverified) => {
    const j = judged.find((x) => x.card.card_id === id);
    const miss = !!(j && j.excluded);
    return {card: byId(id), excluded: unverified || miss, miss: miss, conds: j ? j.conds : [],
      why: miss ? '조건 불일치 — 이 카드는 지금 쓰면 안 된다'
        : unverified ? '미평가 — MES 관측으로 조건을 확인하지 못함'
        : 'Jetson 인용 · ' + (j ? j.why : '로컬 조건 판정 없음')};
  };
  // 카드 원본 title·know_how·safety_basis는 그대로 두고 공지의 stop_conditions만 덧붙인다.
  // 로컬 카드가 없으면 card_id만 남기고 missing 표시(undefined 출력 방지).
  const notices = response.safety_notices || [];
  const safety = notices.map((notice) => {
    const c = byId(notice.card_id);
    if (c && mismatch(c)) return wrongEq(c.card_id);
    return c ? Object.assign({}, c, {safety_basis: c.safety_basis || notice.safety_basis, stop_conditions: notice.stop_conditions || []})
      : {card_id: notice.card_id, missing: true, safety_basis: notice.safety_basis, stop_conditions: notice.stop_conditions || []};
  });
  // 안전 카드는 조치·제외 선택지로 내지 않는다. 공지에 없던 safety_flag 카드도 관문으로 옮긴다(B4).
  const isSafety = (x) => x.card.safety_flag === true || notices.some((n) => n.card_id === x.card.card_id);
  const split = (list) => list.filter((x) => x.card).filter((x) => {
    if (!isSafety(x)) return true;
    if (!safety.some((s) => s.card_id === x.card.card_id)) {
      safety.push(mismatch(x.card) ? wrongEq(x.card.card_id) : Object.assign({}, x.card, {stop_conditions: []}));
    }
    return false;
  });
  const cited = split((response.review_queue ? [] : response.cited_card_ids || []).map((id) => item(id, false)));
  const actions = cited.filter((x) => !x.excluded);
  const excluded = cited.filter((x) => x.excluded).concat(split((response.unverified_card_ids || []).map((id) => item(id, true))));
  return {actions: actions, excluded: excluded, safety: safety, total: actions.length + excluded.length + safety.length};
}

function rankCards(eq, observations = S.observations) {
  const hits = S.cards.filter((c) => cardFits(c, eq));
  // 질의 모드에서 T4 인계 카드는 고정 안전 공지로 올리지 않는다(retrieval.py include_handover).
  const safety = hits.filter((c) => c.safety_flag === true && c.tacit_type !== 'T4');
  const rest = hits.filter((c) => safety.indexOf(c) === -1);

  const scored = rest.map((c) => {
    const conds = (c.conditions || []).map((c) => evalCondition(c, observations));
    const hitExclusions = (c.exclusions || []).map((c) => evalCondition(c, observations)).filter((x) => x.state === 'match');
    const anyMiss = conds.some((x) => x.state === 'miss') || hitExclusions.length > 0;
    const anyMatch = conds.some((x) => x.state === 'match');
    const direct = c.equipment === eq.type;
    const reasons = [];
    if (anyMatch) reasons.push('조건 일치');
    reasons.push(c.mes_equipment_id ? eq.code + ' 지정 카드' : direct ? eq.type + ' 설비 카드' : '공통 카드');
    if (!anyMatch && !anyMiss && conds.length) reasons.push('조건 미평가');
    return {
      card: c, conds: conds.concat(hitExclusions), excluded: anyMiss,
      why: reasons.join(' · '),
      key: [anyMatch ? 0 : 1, direct ? 0 : 1]
    };
  });

  const applicable = scored.filter((x) => !x.excluded)
    .sort((a, b) => a.key[0] - b.key[0] || a.key[1] - b.key[1]);
  const excluded = scored.filter((x) => x.excluded);
  return { safety: safety, actions: applicable, excluded: excluded, total: hits.length };
}

// ── 렌더 ───────────────────────────────────────────────────────────
function safetyEl(c, pin) {
  const d = document.createElement('div');
  d.className = 'safety' + (pin ? ' pin' : '') + (c.mismatch || c.missing ? ' invalid' : '');
  d.innerHTML = '<div class="hd"><span class="dot"></span><span>⚠ 작업 전 안전 확인</span></div>'
    + '<div class="kid"></div><div class="ttl"></div><p class="body" style="margin:0"></p>'
    + '<p class="basis" style="margin:0"></p>'
    + (pin ? '<div class="gate">안전 조건을 확인하고 준수한 뒤 작업하세요.</div>' : '');
  if (c.mismatch) {
    d.querySelector('.kid').textContent = c.card_id + ' · 설비 불일치';
    d.querySelector('.ttl').textContent = '설비 불일치 — ' + c.eqCode + '에 해당하지 않는 안전 공지(' + c.card_id + ')';
    d.querySelector('.basis').textContent = '지침 숨김 — 다른 설비의 안전 지침이므로 표시하지 않습니다. 담당자 확인';
    const gate = d.querySelector('.gate'); if (gate) gate.remove();
    return d;
  }
  d.querySelector('.kid').textContent = c.missing ? c.card_id + ' · 로컬 카드 없음 · 설비 대조 불가' : c.card_id + ' · ' + c.tacit_type + ' · ' + c.grade;
  d.querySelector('.ttl').textContent = c.missing ? '로컬 카드 없음 — 카드 원문을 확인할 수 없어 현재 설비와 대조하지 못했습니다' : c.title;
  d.querySelector('.body').textContent = c.missing ? '' : c.know_how;
  d.querySelector('.basis').textContent = '근거 — ' + (c.safety_basis || '근거 미기재');
  // 서버 공지의 멈춤 조건은 카드 본문을 덮지 않고 따로 붙인다.
  (c.stop_conditions || []).forEach((t) => {
    const p = document.createElement('p');
    p.className = 'stop'; p.textContent = '멈춤 · ' + t;
    d.querySelector('.basis').before(p);
  });
  return d;
}

/* 안전 관문. 화면 상단에 고정하는 것은 얇은 관문 띠 하나뿐이고 카드는 일반 흐름으로 모두 펼친다 —
 * 내부 스크롤 상자나 카드별 sticky는 둘째 카드부터 근거를 가린다(B2). 띠는 pane 직계로 붙어야
 * pane 전체 스크롤 동안 고정되므로 상자는 display:contents(pda.html .safety-stack). */
function safetyStack(cards) {
  const box = document.createElement('div');
  box.className = 'safety-stack';
  const bar = document.createElement('div');
  bar.className = 'safety-bar';
  bar.textContent = '⚠ 작업 전 확인할 안전 수칙 ' + cards.length + '건';
  box.appendChild(bar);
  cards.forEach((c) => box.appendChild(safetyEl(c, true)));
  return box;
}

/* 대화 화면 위 안전 수칙(B1). 평소에는 회색 한 줄로 접고, safetyAlert 일 때만 관문 색으로 펼친다(10/8 최재영 요청).
 * 판정이 그대로면 다시 그리지 않는다 — 작업자가 직접 펼친 상태가 3초 갱신마다 닫히지 않게. */
function renderAskSafety() {
  const box = $('askSafety');
  if (!S.eq) { box.innerHTML = ''; S.safetyView = null; return; }
  const safety = rankCards(S.eq).safety;
  const hot = safetyAlert(S.mes, S.observations, safety);
  const view = S.eq.equipment_id + ':' + safety.length + ':' + hot;
  if (view === S.safetyView) return;
  S.safetyView = view;
  box.innerHTML = '';
  if (!safety.length) return;
  const d = document.createElement('details');
  d.className = 'fold safety-fold' + (hot ? ' hot' : '');
  d.open = hot;
  const sum = document.createElement('summary');
  sum.textContent = hot ? '⚠ 작업 전 확인할 안전 수칙 ' + safety.length + '건 · MES 이상 또는 조건 일치'
    : '안전 수칙 ' + safety.length + '건 · 펼치기';
  d.appendChild(sum);
  safety.forEach((c) => d.appendChild(safetyEl(c, true)));
  box.appendChild(d);
}

const RESTART_TEXT = {normal_stop_restart: '정상 정지 후 재가동', abnormal_stop_restart: '비정상 정지 후 재가동',
  maintenance_restart: '정비 후 재가동'};

function actionEl(item, rank, tried) {
  const c = item.card;
  const d = document.createElement('div');
  d.className = 'card' + (rank === 1 && !tried ? ' top' : '') + (tried ? ' done' : '');
  const head = document.createElement('div');
  head.className = 'rk';
  head.innerHTML = '<span class="rkno' + (rank === 1 && !tried ? ' one' : '') + '">'
    + (rank || '—') + '</span><span class="kid"></span>';
  head.querySelector('.kid').textContent = c.card_id + ' · ' + c.tacit_type + ' · ' + c.grade;
  if (tried) {
    const p = document.createElement('span');
    p.className = 'pill miss'; p.textContent = '시도함 · 효과 없음';
    p.style.marginLeft = 'auto'; head.appendChild(p);
  }
  d.appendChild(head);

  const ttl = document.createElement('div');
  ttl.className = 'ttl'; ttl.textContent = c.title; d.appendChild(ttl);

  const why = document.createElement('div');
  why.className = 'why' + (item.miss ? ' no' : item.excluded || rank !== 1 ? ' dim' : '');
  why.textContent = item.why;
  d.appendChild(why);

  if (item.conds.length) {
    const meta = document.createElement('div');
    meta.className = 'pills';
    item.conds.forEach((r) => {
      const p = document.createElement('span');
      p.className = 'pill ' + r.state; p.textContent = r.text;
      meta.appendChild(p);           // 불일치·미평가도 숨기지 않는다
    });
    d.appendChild(meta);
  }

  // T3 는 카드의 구조화 단계(type_payload.steps)를 order 순서 그대로 보인다(D-28). 단계마다 다음 진행·멈춤·문의처를 함께 둔다.
  const steps = ((c.type_payload || {}).steps || []).slice().sort((a, b) => a.order - b.order);
  if (c.tacit_type === 'T3' && steps.length) {
    const ol = document.createElement('ol'); ol.className = 'steps';
    steps.forEach((s) => {
      const li = document.createElement('li');
      li.innerHTML = '<span class="st"></span><span class="tx"><span class="act"></span></span>';
      li.querySelector('.st').textContent = s.order + '.';
      li.querySelector('.act').textContent = s.action;
      const tx = li.querySelector('.tx');
      const line = (cls, label, text) => {
        if (!text) return;
        const e = document.createElement('span'); e.className = cls; e.textContent = label + text; tx.appendChild(e);
      };
      line('nx', '→ ', s.expected_result);
      (s.stop_conditions || []).forEach((t) => line('stop', '멈춤 · ', t));
      line('nx', '확인 · ', s.verification_step);
      line('nx', '되돌림 · ', s.rollback_action);
      line('esc', '문의 · ', s.escalation_target);
      ol.appendChild(li);
    });
    d.appendChild(ol);
  } else {
    const b = document.createElement('p');
    b.className = 'body'; b.style.margin = '0'; b.textContent = c.know_how;
    d.appendChild(b);
  }

  // T6 는 앞서 해봤지만 안 된 재가동 시도를 남긴다 — 같은 시도를 되풀이하지 않게 결과와 다음 확인을 함께 보인다.
  // 같은 시도를 되풀이한 기록(내용 같고 attempt_id만 다름)은 한 번만 보이고 횟수를 붙인다.
  const tries = [];
  ((c.type_payload || {}).tried_and_failed || []).forEach((a) => {
    const same = tries.find((x) => x.a.action === a.action && x.a.observed_result === a.observed_result);
    if (same) same.n += 1; else tries.push({a: a, n: 1});
  });
  tries.forEach(({a, n}) => {
    const t = document.createElement('div'); t.className = 'tf';
    const row = (cls, text) => {
      if (!text) return;
      const e = document.createElement('span'); e.className = cls; e.textContent = text; t.appendChild(e);
    };
    row('hd', '이전 시도 · ' + (RESTART_TEXT[a.restart_type] || '재가동') + (n > 1 ? ' ' + n + '회' : '') + ' — 안 됨');
    row('act', a.action);
    row('nx', '결과 · ' + (a.observed_result || '기록 없음'));
    if (a.failure_reason) row('nx', '원인 · ' + a.failure_reason);
    (a.next_observations || []).forEach((x) => row('stop', '다음 확인 · ' + x));
    if ((a.required_data || []).length) row('nx', '재가동 전 필요 · ' + a.required_data.join(' · '));
    d.appendChild(t);
  });

  if (c.expected_result) {
    const e = document.createElement('div');
    e.className = 'exp'; e.textContent = '기대 — ' + c.expected_result;
    d.appendChild(e);
  }
  const src = document.createElement('div');
  src.className = 'src'; src.textContent = '출처: 합성 데이터 · split=' + c.split;
  d.appendChild(src);

  if (!item.excluded && !tried) {
    const btn = document.createElement('button');
    btn.type = 'button'; btn.className = 'btn';   // 주 행동 56px(A1)
    btn.textContent = '이 조치 시도';
    btn.addEventListener('click', () => recordTry(c));
    d.appendChild(btn);
  }
  return d;
}

/* 답 말풍선 하나. 순서는 이전 결과 화면과 같다: 안전 카드(해당될 때) → 답 → 근거 카드 ID(펼쳐 보기).
 * 안전 카드를 답보다 앞에 두는 것은 완료 게이트 G2 조건이라 대화형에서도 그대로 둔다. */
function answerBody(turn) {
  const r = turn.ranked, res = turn.response;
  const d = document.createElement('div');
  const none = !res.review_queue && (res.no_knowledge === true || !res.answer);
  d.className = 'msg bot' + (none ? ' none' : '');
  if (r.safety.length) {
    const h = document.createElement('p'); h.className = 'safety-head';
    h.textContent = '⚠ 이 답에 적용되는 안전 수칙 ' + r.safety.length + '건 — 먼저 확인';
    d.appendChild(h);
    r.safety.forEach((c) => d.appendChild(safetyEl(c, true)));
  }
  const answer = document.createElement('p');
  answer.className = 'ans';
  answer.textContent = res.review_queue ? '답변을 보류했습니다. 담당자 검토가 필요합니다.'
    : none ? '해당 지식 없음 — 이 질문에 맞는 근거 카드가 없어 추측으로 답하지 않습니다. 증상을 더 구체적으로 적거나 숙련자에게 문의해 주세요.'
    : res.answer;
  d.appendChild(answer);

  const ids = r.actions.map((x) => x.card.card_id);
  const evidence = res.evidence && res.evidence.equipment_id === S.eq.equipment_id
    ? (res.evidence.measurements || []).filter((m) => m.used_for_conditions && m.equipment_id === S.eq.equipment_id) : [];
  if (!ids.length && !r.excluded.length && !evidence.length) return d;
  const more = document.createElement('details');
  more.className = 'basis-detail';
  const sum = document.createElement('summary');
  sum.textContent = (ids.length ? '근거 카드 ' + ids.join(' · ') : '근거 카드 없음') + ' · 펼쳐 보기';
  more.appendChild(sum);
  if (evidence.length) {
    const label = document.createElement('p'); label.className = 'lbl';
    label.textContent = '질의 당시 MES 센서값 · ' + stamp(res.evidence.simulated_at) + ' · 고정된 답변 근거';
    more.appendChild(label);
    renderSensorReadings(more, evidence);
  }
  // 시도 기록은 마지막 답에만 이어진다(시도 화면이 S.ranked 를 쓴다).
  const triedIds = turn === lastAnswer() ? S.tries.map((t) => t.card_id) : [];
  r.actions.forEach((x, i) => more.appendChild(actionEl(x, i + 1, triedIds.indexOf(x.card.card_id) !== -1)));
  if (r.excluded.length) {
    const l2 = document.createElement('p'); l2.className = 'lbl';
    l2.textContent = '조건 불일치·미평가 ' + r.excluded.length + '건 — 이유와 함께 남김';
    more.appendChild(l2);
    r.excluded.forEach((x) => {
      const el = actionEl(x, null); el.className += ' out' + (x.miss ? ' miss' : ''); more.appendChild(el);
    });
  }
  if (triedIds.length) {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'btn sm ghost';
    b.textContent = '시도 기록 보기 (' + S.tries.length + '건)';
    b.addEventListener('click', () => renderTries());
    more.appendChild(b);
  }
  d.appendChild(more);
  return d;
}

const lastAnswer = () => S.chat.filter((t) => t.status === 'done').slice(-1)[0] || null;

/* 마지막 질문과 답을 인계 메모 초안으로. 메모 칸 최대 길이(4000자)를 넘지 않게 자른다. */
function chatMemo(turn, max = 4000) {
  if (!turn) return '';
  const res = turn.response || {};
  const ids = turn.ranked ? turn.ranked.actions.map((x) => x.card.card_id) : [];
  const answer = res.review_queue ? '답변 보류 · 담당자 검토 필요'
    : (res.no_knowledge === true || !res.answer) ? '해당 지식 없음' : res.answer;
  const text = ['질문: ' + turn.question, '답: ' + answer, ids.length ? '근거 카드: ' + ids.join(', ') : ''].filter(Boolean).join('\n');
  return text.length > max ? text.slice(0, max - 1) + '…' : text;
}

// ── 시도 기록 ──────────────────────────────────────────────────────
function recordTry(card) {
  S.attemptSeq += 1;
  const id = 'AT-' + String(S.attemptSeq).padStart(4, '0');
  const observed = S.observations.length
    ? S.observations.map(obsText).join(', ')
    : '관측값 미입력';
  S.tries.push({
    attempt_id: id, card_id: card.card_id, action: card.title,
    observed_result: observed, failure_reason: '조치 후에도 증상이 유지됨',
    at: new Date().toTimeString().slice(0, 5)
  });
  haptic(30);
  renderTries();
}

function renderTries() {
  const pane = $('triesPane'); pane.innerHTML = '';
  const r = S.ranked;
  if (r && r.safety.length) pane.appendChild(safetyStack(r.safety));

  const lbl = document.createElement('p');
  lbl.className = 'lbl';
  lbl.textContent = '시도 기록 ' + S.tries.length + '건 · 미해결';
  pane.appendChild(lbl);

  S.tries.forEach((t, i) => {
    const d = document.createElement('div');
    d.className = 'try noeff';
    d.innerHTML = '<div class="hd"><span class="rkno">' + (i + 1) + '</span>'
      + '<span class="aid"></span><span class="pill miss" style="margin-left:auto">효과 없음</span></div>'
      + '<div class="fld"><span class="k">조치</span><span class="v a"></span></div>'
      + '<div class="fld"><span class="k">관측</span><span class="v b"></span></div>'
      + '<div class="fld"><span class="k">사유</span><span class="v c"></span></div>';
    d.querySelector('.aid').textContent = t.attempt_id + ' · ' + t.at;
    d.querySelector('.a').textContent = t.card_id + ' ' + t.action;
    d.querySelector('.b').textContent = t.observed_result;
    d.querySelector('.c').textContent = t.failure_reason;
    pane.appendChild(d);
  });

  const triedIds = S.tries.map((t) => t.card_id);
  const next = r ? r.actions.filter((x) => triedIds.indexOf(x.card.card_id) === -1) : [];

  const l2 = document.createElement('p');
  l2.className = 'lbl hot';
  l2.textContent = next.length ? '다음 조치 — 순위가 갱신되었습니다' : '다음 조치 — 남은 조치가 없습니다';
  pane.appendChild(l2);

  const box = document.createElement('div');
  box.className = 'try now';
  if (next.length) {
    box.innerHTML = '<div class="hd"><span class="rkno next">' + (S.tries.length + 1) + '</span>'
      + '<span class="aid"></span><span class="pill" style="margin-left:auto">권장</span></div>'
      + '<div class="fld"><span class="k">조치</span><span class="v a"></span></div>'
      + '<div class="fld"><span class="k">근거</span><span class="v b"></span></div>';
    box.querySelector('.aid').textContent = next[0].card.card_id + ' · ' + next[0].card.tacit_type;
    box.querySelector('.a').textContent = next[0].card.title;
    box.querySelector('.b').textContent = next[0].why + ' — 앞선 조치가 배제되어 순위가 올라감';
  } else {
    box.innerHTML = '<div class="hd"><span class="rkno next">—</span>'
      + '<span class="aid">조치 후보 소진</span>'
      + '<span class="pill" style="margin-left:auto">인계 권장</span></div>'
      + '<div class="fld"><span class="k">상태</span><span class="v a"></span></div>'
      + '<div class="fld"><span class="k">다음</span><span class="v b"></span></div>';
    box.querySelector('.a').textContent = '적용 가능한 조치를 모두 시도했고 전부 배제되었습니다.';
    box.querySelector('.b').textContent = '시도 기록 ' + S.tries.length + '건을 인계로 넘겨 다음 교대가 이어받게 합니다.';
  }
  pane.appendChild(box);

  const spacer = document.createElement('div'); spacer.className = 'grow'; pane.appendChild(spacer);

  const go = document.createElement('button');
  go.type = 'button'; go.className = 'btn primary';
  go.textContent = next.length ? '조치 목록으로' : '인계로 넘기기 (시도 ' + S.tries.length + '건 포함)';
  go.addEventListener('click', () => {
    if (next.length) show('chat');
    else openHandoverNew();
  });
  pane.appendChild(go);

  if (next.length) {
    const alt = document.createElement('button');
    alt.type = 'button'; alt.className = 'btn sm ghost';
    alt.textContent = '인계로 넘기기 (시도 ' + S.tries.length + '건 포함)';
    alt.addEventListener('click', openHandoverNew);
    pane.appendChild(alt);
  }
  show('tries');
}

// ── 대화 질의 ──────────────────────────────────────────────────────
/* 한 번에 한 질문만 보낸다 — Jetson 부하, 그리고 답이 어느 질문의 것인지 섞이지 않게. */
const chatPending = () => S.chat.some((t) => t.status === 'pending');

function renderAskBlock() {
  const btn = $('doSearch');
  btn.disabled = !S.eq || !S.source || chatPending() || !currentQuestion();
  btn.textContent = chatPending() ? '답변 대기' : '보내기';
}

/* 고장 알림 확인 화면의 대상. 탭한 순간의 equipment_id로만 찾는다 — 띠가 다시 그려져도 바뀌지 않는다(B3). */
const alertTarget = (id, equipment) => equipment.find((e) => e.equipment_id === id) || null;

/* 응답을 버려야 하는가 — 취소했거나, 질의를 보낸 뒤 설비가 바뀌었으면 이전 설비의 응답(안전 공지 포함)을 그리지 않는다. */
const staleResponse = (sentEqId, state) => !!state.waitAbort || !state.eq || state.eq.equipment_id !== sentEqId;
const turnGone = (turn) => !S.chat.includes(turn)
  || staleResponse(turn.eqId, {waitAbort: turn.status === 'cancelled', eq: S.eq});

const QUERY_TIMEOUT_MS = 125000;

function userBubble(t) {
  const d = document.createElement('div');
  d.className = 'msg me';
  const q = document.createElement('p'); q.className = 'q'; q.textContent = t.label || t.question;
  d.appendChild(q);
  if (t.label) {   // 짧은 이름 대신 실제로 보낸 문장을 함께 보인다
    const o = document.createElement('p'); o.className = 'orig'; o.textContent = '보낸 문장: ' + t.question;
    d.appendChild(o);
  }
  return d;
}

const waitText = (t) => '답변 작성 중 · ' + Math.floor((Date.now() - t.started) / 1000) + '초';

function botBubble(t) {
  if (t.status === 'done') return answerBody(t);
  const d = document.createElement('div');
  const p = document.createElement('p'); p.className = 'ans';
  d.appendChild(p);
  if (t.status === 'pending') {
    d.className = 'msg bot wait'; d.id = 'turn-' + t.id;
    p.textContent = waitText(t);
    const c = document.createElement('button');
    c.type = 'button'; c.className = 'btn sm ghost'; c.textContent = '취소';
    c.addEventListener('click', () => { t.status = 'cancelled'; renderChat(); renderSymptoms(); renderAskBlock(); });
    d.appendChild(c);
  } else {
    d.className = 'msg bot err';
    p.textContent = t.status === 'cancelled' ? '취소했습니다. 이 질문의 답은 표시하지 않습니다.'
      : '질의 실패 · ' + t.error + ' — 같은 질문을 다시 보내 주세요.';
  }
  return d;
}

function renderChat() {
  const log = $('chatLog'); log.innerHTML = '';
  let last = null;
  S.chat.forEach((t) => { log.appendChild(userBubble(t)); last = botBubble(t); log.appendChild(last); });
  $('chatHandover').hidden = !lastAnswer();
  // 새 답은 머리(안전 카드)부터 보이게 그 말풍선 위쪽으로 스크롤한다.
  if (last && last.scrollIntoView) last.scrollIntoView({block: 'start'});
}

async function sendChat(question, label) {
  question = String(question || '').trim();
  if (!question || !S.eq || !S.source || chatPending()) return;
  const turn = {id: ++S.chatSeq, question: question, label: label && label !== question ? label : '',
    status: 'pending', started: Date.now(), eqId: S.eq.equipment_id};
  S.chat.push(turn);
  if (!label) $('question').value = '';
  S.tries = []; S.attemptSeq = 0;
  renderChat(); renderSymptoms(); renderAskBlock();
  const timer = setInterval(() => {
    const el = $('turn-' + turn.id);
    if (el && turn.status === 'pending') el.querySelector('.ans').textContent = waitText(turn);
  }, 1000);
  try {
    // 메시지 하나 = /api/query 하나. 설비는 scan_id/equipment_id 로 보내고 관측은 MES가 접수 시점 값을 붙인다.
    // 이전 대화는 보내지 않는다 — 10/14 채점·hybrid 측정이 한 질문 구조로 사전 등록돼 있다.
    const res = await api('/api/query', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(queryApiPayload(question, S))}, QUERY_TIMEOUT_MS);
    const response = await res.json();
    if (turnGone(turn)) return;
    if (!res.ok) throw new Error(response.error || 'HTTP ' + res.status);
    const readings = response.evidence && response.evidence.equipment_id === turn.eqId
      ? (response.evidence.measurements || []).filter((m) => m.used_for_conditions && m.equipment_id === turn.eqId) : [];
    turn.response = response;
    turn.ranked = responseCards(response, S.cards, rankCards(S.eq, readings), S.eq);
    turn.status = 'done';
    S.queryResponse = response; S.ranked = turn.ranked;
    if (turn.ranked.safety.length) haptic([120]);
  } catch (err) {
    if (turnGone(turn)) return;
    turn.status = 'error';
    turn.error = err && err.name === 'AbortError' ? '응답 시간 초과' : String(err && err.message || err);
  } finally {
    clearInterval(timer);
  }
  if (S.screen === 'chat') { renderChat(); renderSymptoms(); }
  renderAskBlock();
}

const HANDOVER_STATUS = {
  open: ['조치 필요', '아직 완료되지 않아 다음 교대에서 처리해야 하는 항목입니다.'],
  in_progress: ['진행 중', '조치를 시작했으며 완료 확인이 남아 있는 항목입니다.'],
  needs_recheck: ['재확인 필요', '이전 조치나 확인 결과를 다시 검토해야 하는 항목입니다. 완료로 처리하지 않습니다.'],
  done: ['완료', '완료로 기록된 항목입니다.'],
  closed: ['종료', '종료로 기록된 항목입니다.'],
  withdrawn: ['철회', '처리 대상에서 철회된 항목입니다.'],
};
function handoverStatus(status) {
  return HANDOVER_STATUS[status] || ['상태 확인 필요', '등록된 상태를 담당자에게 확인해 주세요.'];
}

function appendBasisDetails(parent, ids) {
  if (!ids.length) {
    const p = document.createElement('p'); p.className = 'hint'; p.textContent = '등록된 근거가 없습니다.';
    parent.appendChild(p); return;
  }
  ids.forEach((id) => {
    const record = S.cards.find((c) => c.card_id === id) || S.basisRecords[id];
    const detail = document.createElement('details'); detail.className = 'basis-detail';
    const summary = document.createElement('summary');
    summary.textContent = '근거 보기 · ' + id + (record && record.title ? ' · ' + record.title : '');
    detail.appendChild(summary);
    const p = document.createElement('p'); p.className = 'body';
    if (!record) p.textContent = '이 근거의 원문을 찾을 수 없습니다. 담당자에게 확인해 주세요.';
    else if (record.card_id) p.textContent = [record.know_how, record.rationale, record.safety_basis].filter(Boolean).join('\n\n');
    else if (record.detail) p.textContent = [record.detail, record.executed_at].filter(Boolean).join('\n');
    else p.textContent = ['결과: ' + ({improved:'개선됨', unchanged:'변화 없음', worsened:'악화됨'}[record.immediate_result] || record.immediate_result || '미기재'),
      '기록 시각: ' + (record.recorded_at || '미기재'),
      '관찰 기간: ' + (record.observation_window_h == null ? '미기재' : record.observation_window_h + '시간'),
      ...(record.post_measurements || []).map((m) => signalName(m.signal) + ' ' + m.value + ' ' + unitText(m.unit))].join('\n');
    detail.appendChild(p); parent.appendChild(detail);
  });
}

function openHandover() {
  const pane = $('hoPane'); pane.innerHTML = '';
  const mine = S.handovers.filter((h) =>
    (h.open_items || []).some((it) => String(it.text).indexOf(S.eq ? S.eq.code : '§') !== -1)
    || !S.eq);
  const list = mine.length ? mine : S.handovers;

  if (!list.length) {
    const p = document.createElement('p');
    p.className = 'hint'; p.textContent = '등록된 인계 기록이 없습니다.';
    pane.appendChild(p); show('handover'); return;
  }
  list.forEach((h) => {
    const l = document.createElement('p');
    l.className = 'lbl';
    l.textContent = h.handover_id + ' · ' + h.shift_from + '조 → ' + h.shift_to + '조 · ' + h.shift_date;
    pane.appendChild(l);

    const memo = document.createElement('div');
    memo.className = 'card';
    memo.innerHTML = '<div class="kid">전 교대 메모</div><p class="body" style="margin:0"></p>';
    memo.querySelector('.body').textContent = h.memo_text;
    pane.appendChild(memo);

    const open = (h.open_items || []).filter((it) => !['closed', 'done', 'withdrawn'].includes(it.status));
    const l2 = document.createElement('p');
    l2.className = 'lbl'; l2.textContent = '처리 또는 재확인이 필요한 항목 ' + open.length + '건';
    pane.appendChild(l2);
    const legend = document.createElement('p'); legend.className = 'hint';
    legend.textContent = '인계 기록에 등록된 상태입니다. MES 수치가 정상으로 돌아와도 자동으로 완료 처리하지 않습니다.';
    pane.appendChild(legend);

    open.forEach((it) => {
      const d = document.createElement('div');
      d.className = 'card';
      d.innerHTML = '<div class="pills"><span class="pill miss st"></span>'
        + '<span class="pill du"></span></div>'
        + '<p class="body" style="margin:0"></p><div class="src"></div>';
      const st = d.querySelector('.st');
      const status = handoverStatus(it.status);
      st.textContent = status[0];
      const explanation = document.createElement('p');
      explanation.className = 'hint'; explanation.textContent = status[1];
      d.querySelector('.pills').after(explanation);
      if (it.status !== 'open') st.className = 'pill unknown st';
      d.querySelector('.du').textContent = it.due_shift + '조 마감';
      d.querySelector('.body').textContent = it.text;
      appendBasisDetails(d.querySelector('.src'), it.basis_ids || []);
      pane.appendChild(d);
    });
  });
  show('handover');
}

const HANDOVER_PENDING_KEY = 'shiftlink.handover.pending';

async function submitHandover(note, request = api, store = localStorage) {
  const pending = JSON.parse(store.getItem(HANDOVER_PENDING_KEY) || 'null');
  if (pending && (pending.memo_text !== note.memo_text ||
      JSON.stringify(pending.required_context) !== JSON.stringify(note.required_context))) {
    throw new Error('pending 인계가 남아 있습니다. 인계 화면을 다시 열어 기존 메모를 재전송하세요.');
  }
  // PDA may use the Jetson's plain HTTP LAN address (randomUUID needs a secure context).
  const id = globalThis.crypto && typeof globalThis.crypto.randomUUID === 'function'
    ? globalThis.crypto.randomUUID() : Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);
  const payload = pending || Object.assign({}, note, {handover_id: 'HO-' + id});
  store.setItem(HANDOVER_PENDING_KEY, JSON.stringify(payload));
  const response = await request('/api/handover', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(payload)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '인계 저장 실패');
  store.removeItem(HANDOVER_PENDING_KEY);
  return result;
}

/* memo: 대화에서 넘어올 때 마지막 질문·답 초안(chatMemo). 버튼 클릭 이벤트가 인자로 오면 무시한다. */
function openHandoverNew(memo) {
  S.hoNewBack = S.screen === 'chat' ? 'chat' : 'ctx';
  if (typeof memo === 'string' && memo) $('hoMemo').value = memo;
  const ctx = S.tries.length
    ? '시도 ' + S.tries.length + '건 실패 (' + S.tries.map((t) => t.attempt_id).join(' · ') + ')'
      + (S.observations.length ? ' · ' + S.observations.map(obsText).join(', ') : '')
    : (S.observations.length
        ? S.observations.map(obsText).join(', ')
        : '시도 기록 없음 — 직접 입력 필요');
  $('hoCtx').value = ctx;
  $('hoLoadMes').disabled = false;
  $('hoMesStatus').textContent = '현재 측정값과 최근 이벤트를 작업 상황에 추가합니다.';
  $('hoSave').textContent = '저장';
  try {
    const pending = JSON.parse(localStorage.getItem(HANDOVER_PENDING_KEY) || 'null');
    if (pending) {
      $('hoLoadMes').disabled = true;
      $('hoMesStatus').textContent = '전송 확인이 안 된 인계입니다. 기존 내용으로 재전송해 주세요.';
      $('hoSave').textContent = '대기 인계 재전송 · ' + pending.handover_id;
      $('hoMemo').value = pending.memo_text;
      ['hoRole','hoTiming','hoChannel','hoAck'].forEach((id, index) => {
        $(id).value = pending.required_context[['recipient_role','timing','channel','acknowledgement'][index]];
      });
      $('hoCtx').value = pending.required_context.context;
    }
  } catch (err) {
    $('hoWarn').hidden = false;
    $('hoWarn').textContent = '인계 대기 기록을 읽지 못했습니다: ' + err.message;
    $('hoSave').disabled = true; show('hoNew'); return;
  }
  validateHandover();
  show('hoNew');
}

function mesHandoverContext(snap, events, eq) {
  const readings = usableReadings(snap, eq).kept;
  const recent = (events || []).filter((e) => e.equipment_id === eq.equipment_id).slice(-5);
  return ['MES 기록 · ' + eq.code + ' · ' + snap.simulated_at,
    ...readings.map((m) => (eq.signals.find((spec) => spec.signal === m.signal).name || m.signal) + ': ' + m.value + ' ' + unitText(m.unit) + ' · 측정 ' + m.observed_at),
    ...recent.map((e) => e.occurred_at + ' · ' + e.observation)].join('\n');
}

async function importHandoverMes() {
  const eq = S.eq;
  if (!eq) { $('hoMesStatus').textContent = '설비를 먼저 선택해 주세요.'; return; }
  const button = $('hoLoadMes'); button.disabled = true;
  $('hoMesStatus').textContent = 'MES 기록을 불러오는 중…';
  try {
    const [snap, log] = await Promise.all([getJson('/api/state'), getJson('/api/events')]);
    if (S.eq !== eq || S.screen !== 'hoNew') return;
    const text = mesHandoverContext(snap, log.events, eq);
    const input = $('hoCtx');
    const combined = [input.value.trim(), text].filter(Boolean).join('\n\n');
    if (combined.length > input.maxLength) throw new Error('입력 가능한 글자 수를 초과합니다. 기존 내용을 줄인 뒤 다시 불러와 주세요.');
    input.value = combined;
    $('hoMesStatus').textContent = 'MES 기록을 추가했습니다. 필요한 내용을 수정해 주세요.';
    validateHandover();
  } catch (err) { $('hoMesStatus').textContent = 'MES 기록을 불러오지 못했습니다. ' + err.message; }
  finally { button.disabled = false; }
}

function validateHandover() {
  const ok = ['hoMemo', 'hoCtx', 'hoRole', 'hoTiming', 'hoChannel', 'hoAck'].every((id) => $(id).value.trim());
  $('hoSave').disabled = !ok;
  $('hoWarn').hidden = ok;
}


function outboxLabels(body) {
  const handover = (body && body.handover) || {};
  const pending = Number(handover.pending) || 0;
  const conflict = Number(handover.conflict) || 0;
  return {
    pending: pending > 0 ? '업로드 대기 ' + pending + '건' : '',
    conflict: conflict > 0 ? '확인 필요 ' + conflict + '건' : '',
  };
}

function paintOutbox(labels) {
  if (typeof document === 'undefined') return;
  [['homePending', 'hoPending', labels.pending], ['homeConflict', 'hoConflict', labels.conflict]]
    .forEach(([a, b, text]) => {
      [a, b].forEach((id) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.textContent = text;
        el.hidden = !text;
      });
    });
}

async function refreshOutbox(request) {
  const ask = request || (typeof fetch === 'function' ? fetch : null);
  if (!ask) return outboxLabels(null);
  try {
    const res = await ask('/api/outbox', {cache: 'no-store'});
    if (!res || !res.ok) return outboxLabels(null);
    return outboxLabels(await res.json());
  } catch (_) {
    return outboxLabels(null);
  }
}

/* 업로드 대기 인계 1건 → 화면 문구. 원문 메모는 그대로 보여 준다. */
function outboxItemView(h, equipment) {
  const eq = (equipment || []).find((e) => e.equipment_id === h.equipment_id);
  const ctx = h.required_context || {};
  const when = new Date(h.created_at);
  return {
    kid: h.handover_id + ' · ' + (isNaN(when) ? '' : when.toLocaleString('ko-KR')),
    memo: h.memo_text || '',
    lines: [
      '설비 ' + (eq ? eq.code : (h.equipment_id || '지정 안 함')),
      ctx.recipient_role ? '받는 사람 ' + ctx.recipient_role : '',
      ctx.timing ? '전달 시점 ' + ctx.timing : '',
      '시도 ' + (h.attempts || []).length + '건 · 관찰 ' + (h.observations || []).length + '건',
    ].filter(Boolean),
  };
}

async function openOutbox() {
  const back = S.screen;
  $('obBack').onclick = () => show(back);
  const pane = $('obPane');
  pane.innerHTML = '<p class="hint">불러오는 중…</p>';
  show('outbox');
  let list;
  try { list = (await getJson('/api/outbox/pending')).handovers || []; }
  catch (_) { pane.innerHTML = '<p class="hint">MES에서 대기 목록을 불러오지 못했습니다.</p>'; return; }
  pane.innerHTML = '<p class="hint">MES(Jetson)에 저장되어 있고, 클라우드로 아직 올라가지 않은 인계입니다. 지워지지 않습니다.</p>';
  if (!list.length) pane.insertAdjacentHTML('beforeend', '<p class="hint">대기 중인 인계가 없습니다.</p>');
  list.forEach((h) => {
    const v = outboxItemView(h, S.equipment);
    const d = document.createElement('div');
    d.className = 'card';
    d.innerHTML = '<div class="kid"></div><p class="body" style="margin:0;color:var(--tx)"></p><div class="src"></div>';
    d.querySelector('.kid').textContent = v.kid;
    d.querySelector('.body').textContent = v.memo;
    d.querySelector('.src').textContent = v.lines.join(' · ');
    pane.appendChild(d);
  });
}

const HANGUL_CHO = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ';
const HANGUL_JUNG = 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ';
const HANGUL_JONG = 'ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ';
const HANGUL_JUNG_COMB = { 'ㅗㅏ':'ㅘ', 'ㅗㅐ':'ㅙ', 'ㅗㅣ':'ㅚ', 'ㅜㅓ':'ㅝ', 'ㅜㅔ':'ㅞ', 'ㅜㅣ':'ㅟ', 'ㅡㅣ':'ㅢ' };
const HANGUL_JONG_COMB = { 'ㄱㅅ':'ㄳ', 'ㄴㅈ':'ㄵ', 'ㄴㅎ':'ㄶ', 'ㄹㄱ':'ㄺ', 'ㄹㅁ':'ㄻ', 'ㄹㅂ':'ㄼ', 'ㄹㅅ':'ㄽ', 'ㄹㅌ':'ㄾ', 'ㄹㅍ':'ㄿ', 'ㄹㅎ':'ㅀ', 'ㅂㅅ':'ㅄ' };
const HANGUL_JONG_SPLIT = { 'ㄳ':['ㄱ','ㅅ'], 'ㄵ':['ㄴ','ㅈ'], 'ㄶ':['ㄴ','ㅎ'], 'ㄺ':['ㄹ','ㄱ'], 'ㄻ':['ㄹ','ㅁ'], 'ㄼ':['ㄹ','ㅂ'], 'ㄽ':['ㄹ','ㅅ'], 'ㄾ':['ㄹ','ㅌ'], 'ㄿ':['ㄹ','ㅍ'], 'ㅀ':['ㄹ','ㅎ'], 'ㅄ':['ㅂ','ㅅ'] };

function emptyHangul() { return { done: '', cho: -1, jung: -1, jong: 0 }; }

function hangulSyllable(st) {
  if (st.cho < 0) return '';
  if (st.jung < 0) return HANGUL_CHO[st.cho];
  return String.fromCharCode(0xAC00 + (st.cho * 21 + st.jung) * 28 + st.jong);
}

function hangulText(st) { return st.done + hangulSyllable(st); }

function hangulPress(st, key) {
  st = { done: st.done, cho: st.cho, jung: st.jung, jong: st.jong };
  if (key === '⌫') {
    if (st.jong > 0) {
      const split = HANGUL_JONG_SPLIT[HANGUL_JONG[st.jong - 1]];
      st.jong = split ? HANGUL_JONG.indexOf(split[0]) + 1 : 0;
      return st;
    }
    if (st.jung >= 0) { st.jung = -1; return st; }
    if (st.cho >= 0) { st.cho = -1; return st; }
    st.done = Array.from(st.done).slice(0, -1).join('');
    return st;
  }
  const cho = HANGUL_CHO.indexOf(key);
  const jung = HANGUL_JUNG.indexOf(key);
  if (st.cho < 0) {
    if (cho >= 0) st.cho = cho;
    else st.done += key;
    return st;
  }
  if (st.jung < 0) {
    if (jung >= 0) st.jung = jung;
    else {
      st.done += hangulSyllable(st);
      st.cho = cho;
      st.jung = -1;
      st.jong = 0;
      if (cho < 0) st.done += key;
    }
    return st;
  }
  if (jung >= 0 && st.jong === 0) {
    const comb = HANGUL_JUNG_COMB[HANGUL_JUNG[st.jung] + key];
    if (comb) { st.jung = HANGUL_JUNG.indexOf(comb); return st; }
  }
  if (cho >= 0 && st.jong === 0 && HANGUL_JONG.includes(key)) {
    st.jong = HANGUL_JONG.indexOf(key) + 1;
    return st;
  }
  if (cho >= 0 && st.jong > 0) {
    const comb = HANGUL_JONG_COMB[HANGUL_JONG[st.jong - 1] + key];
    if (comb) { st.jong = HANGUL_JONG.indexOf(comb) + 1; return st; }
    st.done += hangulSyllable(st);
    st.cho = cho; st.jung = -1; st.jong = 0;
    return st;
  }
  if (jung >= 0 && st.jong > 0) {
    const tail = HANGUL_JONG[st.jong - 1];
    const split = HANGUL_JONG_SPLIT[tail];
    const move = split ? split[1] : tail;
    st.jong = split ? HANGUL_JONG.indexOf(split[0]) + 1 : 0;
    st.done += hangulSyllable(st);
    st.cho = HANGUL_CHO.indexOf(move);
    st.jung = jung;
    st.jong = 0;
    return st;
  }
  st.done += hangulSyllable(st);
  return hangulPress({ done: st.done, cho: -1, jung: -1, jong: 0 }, key);
}

// Node 테스트는 DOM 없이 순수 함수만 쓴다.
// 임계값·통과 장수는 서버 /api/face/config 와 프레임 응답이 준다. 여기 숫자는 두지 않는다.
function faceVerdict(scores, threshold, need, max) {
  const passed = scores.filter((score) => score >= threshold).length;
  if (passed >= need) return 'pass';
  if (scores.length >= max) return 'fail';
  return 'wait';
}

if (typeof module !== 'undefined') { module.exports = { unityLocation, handoverStatus, mesHandoverContext, S, equipmentFrom, stateOf, usableReadings, evalCondition, rankCards, cardFits, obsView, queryApiPayload, responseCards, scanTarget, staleResponse, submitHandover, outboxLabels, refreshOutbox, outboxItemView, equipmentFromLink, symptomsFor, alertOrder, releaseContext, alertTarget, failScan, hangulPress, hangulText, emptyHangul, faceVerdict, stopFaceCamera, safetyAlert, answerBody, chatMemo }; }
if (typeof document !== 'undefined') {

// ── 배선 ───────────────────────────────────────────────────────────
function on(id, fn) { const el = $(id); if (el) el.addEventListener('click', fn); }

let loginHangul = emptyHangul();

function mountLoginHangul() {
  const box = $('loginHangul');
  if (!box || box.childElementCount) return;
  const rows = ['ㅂㅈㄷㄱㅅㅛㅕㅑㅐㅔ', 'ㅁㄴㅇㄹㅎㅗㅓㅏㅣ', 'ㅋㅌㅊㅍㅠㅜㅡ', '⌫'];
  rows.forEach((chars) => {
    const row = document.createElement('div');
    row.className = 'row';
    Array.from(chars).forEach((ch) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = ch;
      btn.addEventListener('click', () => {
        loginHangul = hangulPress(loginHangul, ch);
        $('loginName').value = hangulText(loginHangul);
      });
      row.appendChild(btn);
    });
    box.appendChild(row);
  });
}

function loginError(text) {
  const el = $('loginErr');
  el.hidden = !text;
  el.textContent = text || '';
}

function submitLogin() {
  const name = $('loginName').value.trim();
  const id = $('loginId').value.trim();
  if (!name || !id) {
    loginError('이름과 사번을 모두 입력하세요.');
    return;
  }
  loginError('');
  S.operator = { name: name, id: id };
  show('face');
  startFaceCamera();
}

let toastTimer = 0;

function showToast(text) {
  const el = $('toast');
  if (!el) return;
  el.hidden = false;
  el.textContent = text;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 2000);
}

// 대시보드(Jetson 주소)에 갔다 돌아오면 pda.html을 새로 연다. 같은 탭 동안만 로그인을 기억한다 —
// 종료·재시작으로 키오스크 창이 새로 뜨면 sessionStorage가 비어 다시 로그인한다. 얼굴 데이터는 두지 않는다.
const OPERATOR_KEY = 'shiftlink.operator';
function savedOperator() {
  try {
    const o = JSON.parse(sessionStorage.getItem(OPERATOR_KEY) || 'null');
    return o && o.name && o.id ? o : null;
  } catch (_) { return null; }
}

afterBoot = () => {
  const saved = savedOperator();
  if (saved) { S.operator = saved; enterWork(); } else show('login');
};

function enterWork() {
  try { sessionStorage.setItem(OPERATOR_KEY, JSON.stringify(S.operator)); } catch (_) { /* 저장 못 하면 돌아올 때 다시 로그인 */ }
  if (S.operator && S.operator.name) showToast(S.operator.name + '님 로그인 되었습니다');
  if (S.linkedEquipment) {
    setContext(S.linkedEquipment, 'unity_link');
    show('ctx');
  } else {
    show('home');
  }
}

/* 프레임은 이 기기(/api/face/frame)에서만 점수 낸다. 저장하거나 Jetson으로 보내지 않는다(D-42). */
function setFaceStatus(kind, text) {
  const el = $('faceState');
  el.classList.toggle('ok', kind === 'pass');
  el.classList.toggle('failed', kind === 'fail');
  $('faceText').textContent = text;
}

function wait(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

async function loadFaceRule() {
  const res = await fetch('/api/face/config');
  if (!res.ok) throw new Error('face config');
  return res.json();
}

async function watchFace(run) {
  let rule;
  try {
    rule = await loadFaceRule();
  } catch (err) {
    setFaceStatus('fail', '얼굴 확인 설정을 읽지 못했습니다');
    $('faceRetry').hidden = false;
    return;
  }
  $('faceBypass').hidden = !rule.bypass;
  const video = $('faceVideo');
  const canvas = document.createElement('canvas');
  canvas.width = 640;
  canvas.height = 480;
  const ctx = canvas.getContext('2d');
  const scores = [];
  setFaceStatus('', '얼굴을 확인하는 중…');
  $('faceRetry').hidden = true;
  while (run === faceRun && S.screen === 'face') {
    if (video.readyState < 2) { await wait(200); continue; }
    ctx.drawImage(video, 0, 0, 640, 480);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.85));
    if (!blob || run !== faceRun) return;
    let data;
    try {
      const res = await fetch('/api/face/frame', {
        method: 'POST',
        headers: { 'Content-Type': 'image/jpeg', 'X-Employee-Id': S.operator.id },
        body: blob,
      });
      data = await res.json();
      if (!res.ok) {
        setFaceStatus('fail', data.error || '얼굴 확인에 실패했습니다');
        $('faceRetry').hidden = false;
        if (data.bypass) $('faceBypass').hidden = false;
        return;
      }
    } catch (err) {
      setFaceStatus('fail', '얼굴 확인에 실패했습니다');
      $('faceRetry').hidden = false;
      return;
    }
    if (!data.face) {
      setFaceStatus('', '얼굴이 안 보입니다');
    } else {
      scores.push(data.score);
      const passed = scores.filter((score) => score >= data.threshold).length;
      const verdict = faceVerdict(scores, data.threshold, data.need, data.frames);
      if (verdict === 'pass') {
        setFaceStatus('pass', '통과');
        await wait(800);
        if (run === faceRun && S.screen === 'face') enterWork();
        return;
      }
      if (verdict === 'fail') {
        setFaceStatus('fail', '거절');
        $('faceRetry').hidden = false;
        return;
      }
      setFaceStatus('', '확인 중 ' + passed + '/' + data.need);
    }
    await wait(350);
  }
}

async function startFaceCamera() {
  stopFaceCamera();
  const run = faceRun;
  const video = $('faceVideo');
  $('faceWho').textContent = S.operator.name + ' · ' + S.operator.id;
  $('faceRetry').hidden = true;
  setFaceStatus('', '카메라를 여는 중…');
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    setFaceStatus('fail', '이 브라우저에서 카메라를 열 수 없습니다.');
    return;
  }
  try {
    faceStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
      audio: false,
    });
    if (S.screen !== 'face' || run !== faceRun) { stopFaceCamera(); return; }
    video.srcObject = faceStream;
    await video.play();
    watchFace(run);
  } catch (err) {
    setFaceStatus('fail', '카메라를 열 수 없습니다. 다른 프로그램이 카메라를 쓰고 있으면 닫아 주세요.');
  }
}

['loginName', 'loginId'].forEach((id) => {
  $(id).addEventListener('keydown', (ev) => { if (ev.key === 'Enter') submitLogin(); });
});
on('loginGo', submitLogin);
on('faceBack', () => show('login'));
on('faceRetry', () => { startFaceCamera(); });
on('faceBypass', enterWork);
on('pdaExit', () => { try { sessionStorage.removeItem(OPERATOR_KEY); } catch (_) {} fetch('/api/pda/exit', { method: 'POST' }).catch(() => {}); });
document.querySelectorAll('.home').forEach((b) => b.addEventListener('click', () => show('home')));
on('toScan', startScan);
on('scanClose', () => show('home'));
on('scanManual', openManual);
on('toManual', openManual);
on('manualClose', () => show(S.eq ? 'ctx' : 'home'));
on('manualToScan', startScan);
on('ctxBack', () => show('home'));
on('ctxEdit', startScan);
on('toAsk', () => { renderSymptoms(); renderObsList(); renderAskBlock(); show('chat'); loadMesObservations(); });
on('obsReload', () => loadMesObservations());
on('askBack', () => show('ctx'));
on('doSearch', () => sendChat(currentQuestion()));
on('triesBack', () => show('chat'));
on('chatHandover', () => openHandoverNew(chatMemo(lastAnswer())));
on('toHandover', openHandover);
on('toHandoverHome', openHandover);
on('homePending', openOutbox);
on('hoPending', openOutbox);
on('hoBack', () => show(S.eq ? 'ctx' : 'home'));
on('toHandoverNew', openHandoverNew);
on('hoNewBack', () => show(S.hoNewBack || 'ctx'));
on('hoLoadMes', importHandoverMes);
on('hoSave', async () => {
  $('hoSave').disabled = true;
  $('hoWarn').hidden = false;
  $('hoWarn').textContent = 'MES에 인계를 저장하고 있습니다…';
  try {
    const result = await submitHandover({memo_text:$('hoMemo').value.trim(),
      equipment_id:S.eq ? S.eq.equipment_id : null,
      required_context:{recipient_role:$('hoRole').value.trim(), timing:$('hoTiming').value.trim(),
        channel:$('hoChannel').value.trim(), acknowledgement:$('hoAck').value.trim(), context:$('hoCtx').value.trim()},
      attempts:S.tries, observations:S.observations});
    haptic([120]);
    $('hoWarn').textContent = 'MES 로컬 저장 완료 · ' + result.handover_id;
    pollOutbox();   // 저장 즉시 '업로드 대기' 반영 — 다음 주기까지 기다리지 않는다
  } catch (err) {
    $('hoWarn').textContent = '저장 확인 실패 · ' + err.message + ' · 같은 메모로 다시 저장하면 재전송됩니다.';
    $('hoSave').disabled = false;
  }
});
['hoMemo','hoCtx','hoRole','hoTiming','hoChannel','hoAck'].forEach((id) => {
  $(id).addEventListener('input', validateHandover);
});

$('question').addEventListener('input', renderAskBlock);
// Enter 로 보내고 Shift+Enter 는 줄바꿈. 한글 조합 중 Enter 는 조합 확정이므로 보내지 않는다.
$('question').addEventListener('keydown', (ev) => {
  if (ev.key === 'Enter' && !ev.shiftKey && !ev.isComposing) { ev.preventDefault(); sendChat(currentQuestion()); }
});
$('obsSignal').addEventListener('change', renderObsRange);
on('obsAdd', () => {
  const sel = $('obsSignal'), val = $('obsValue');
  if (!sel.value || val.value === '') return;
  const meta = S.eq.signals.find((x) => x.signal === sel.value) || { unit: '' };
  const value = Number(val.value);
  if (!Number.isFinite(value) || (meta.unit === 'bool' && value !== 0 && value !== 1)) return;
  S.observations = S.observations.filter((o) => o.signal !== sel.value);
  S.observations.push({ signal: sel.value, unit: meta.unit, value: value, source: 'manual' });
  val.value = ''; renderObsList();
});


// ── MES 실시간 감시 ────────────────────────────────────────────────
/* ponytail: 3초 폴링. 푸시(SSE)는 파이 프록시와 MES 서버를 둘 다 고쳐야 해서 보류 — 지연이 문제면 그때. */
const WATCH_MS = 3000;
const ALERT_ROWS = 3;

/* 설비별 고장 상황: 경보 · MES 증상 후보 · 범위 이탈 · 자체 이상. 원인은 확정하지 않는다. */
function faultsFrom(snap) {
  return S.equipment.map((eq) => {
    const items = [];
    (snap.active_alarms || []).filter((a) => a.equipment_id === eq.equipment_id).forEach((a) => items.push('경보 ' + (a.label || a.code)));
    (snap.symptom_diagnostics || []).filter((d) => d.equipment_id === eq.equipment_id)
      .forEach((d) => items.push(d.symptom + '(확정 아님)'));
    const state = (snap.equipment || []).find((e) => e.equipment_id === eq.equipment_id) || {};
    usableReadings(snap, eq).kept.forEach((o) => {
      const spec = eq.signals.find((x) => x.signal === o.signal);
      if (spec && spec.zeroStopped && o.value === 0 && state.operating_state !== 'running') return;
      const st = stateOf(spec, o.value);
      if (st === 'low' || st === 'high') items.push(String(spec.name).split(' (')[0] + (st === 'low' ? ' ▼' : ' ▲'));
    });
    if (!items.length && state.fault_level && state.fault_level !== 'normal') items.push(STATE_TXT[state.fault_level] || state.fault_level);
    const alarms = (snap.active_alarms || []).filter((a) => a.equipment_id === eq.equipment_id);
    const level = alarms.some((a) => a.severity === 'critical') || state.fault_level === 'critical' ? 0
      : alarms.length || (state.fault_level && state.fault_level !== 'normal') ? 1 : 2;
    return { eq: eq, items: items, level: level, at: alarms.map((a) => a.raised_at).sort()[0] || '' };
  }).filter((f) => f.items.length);
}

function renderAlert(faults) {
  const el = $('alert');
  const key = faults.map((f) => f.eq.code + f.items.join()).join('|');
  // 내용이 같으면 다시 그리지 않는다 — 누르는 도중 다시 그리면 클릭이 사라진다.
  S.faults = faults;
  const view = key + '@' + (S.eq ? S.eq.code : '');   // 선택 설비를 먼저 보이므로 설비가 바뀌면 다시 그린다
  if (view === S.alertView) return;
  if (key && key !== S.alertKey) haptic([80, 60, 80]);
  S.alertKey = key; S.alertView = view;
  el.hidden = !faults.length;
  el.innerHTML = '';
  // 선택 설비를 맨 위에. ponytail: 3줄까지만 보이고 나머지는 대수만 — 동시 고장이 흔해지면 목록 화면으로.
  const sorted = alertOrder(faults, S.eq);
  sorted.slice(0, ALERT_ROWS).forEach((f) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'alrow';
    b.innerHTML = '<span class="t"></span><span class="go">확인 ›</span>';
    b.querySelector('.t').textContent = '⚠ ' + f.eq.code + ' 고장 상황 · ' + f.items.join(' · ');
    // 설비를 바로 바꾸지 않는다 — 확인 화면에서 code를 크게 보이고 하단 버튼으로만 확정한다(B3·A4).
    const pick = { equipment_id: f.eq.equipment_id, items: f.items.slice() };
    b.addEventListener('click', () => openAlertGo(pick));
    el.appendChild(b);
  });
  if (sorted.length > ALERT_ROWS) {
    const more = document.createElement('p');
    more.className = 'almore';
    more.textContent = '외 ' + (sorted.length - ALERT_ROWS) + '대 고장 — ' + sorted.slice(ALERT_ROWS).map((f) => f.eq.code).join(', ');
    el.appendChild(more);
  }
}

function openAlertGo(pick) {
  const eq = alertTarget(pick.equipment_id, S.equipment);
  if (!eq) return;
  S.alertPick = pick.equipment_id;
  // 스캔·대기 화면은 돌아가도 이어지지 않으므로 작업 선택(또는 홈)으로 돌린다.
  S.alertBack = ['scan', 'wait', 'boot', 'alertGo'].includes(S.screen) ? (S.eq ? 'ctx' : 'home') : S.screen;
  $('alertGoCode').textContent = eq.code;
  $('alertGoName').textContent = eq.group + (eq.where ? ' · ' + eq.where : '');
  $('alertGoItems').textContent = pick.items.join(' · ');
  $('alertGoNow').textContent = S.eq === eq ? '지금 선택된 설비입니다.'
    : (S.eq ? '지금 설비 ' + S.eq.code + ' → ' + eq.code + '(으)로 바뀝니다.' : eq.code + '(으)로 설비를 확정합니다.');
  show('alertGo');
}
on('alertGoOk', () => {
  const eq = alertTarget(S.alertPick, S.equipment);
  S.alertPick = null;
  if (!eq) { show(S.eq ? 'ctx' : 'home'); return; }
  if (S.eq !== eq) setContext(eq, 'manual_selection', {});
  haptic(30);
  $('toAsk').click();
  renderAlert(S.faults);   // 고른 설비를 띠 맨 위로
});
const alertGoLeave = () => { S.alertPick = null; show(S.alertBack || (S.eq ? 'ctx' : 'home')); };
on('alertGoCancel', alertGoLeave);
on('alertGoBack', alertGoLeave);

async function watchMes() {
  if (S.equipment.length) {
    try {
      const snap = await getJson('/api/state');
      renderAlert(faultsFrom(snap));
      if (S.eq) await loadMesObservations(snap);
    } catch (err) { if (S.eq) clearMesObservations(); console.warn('MES 감시 실패', err); }
  }
  setTimeout(watchMes, WATCH_MS);
}

// ── 기동 ───────────────────────────────────────────────────────────
renderNet();
mountLoginHangul();
window.paintOutbox = paintOutbox;
async function pollOutbox() { paintOutbox(await refreshOutbox()); }
probeServer();
pollOutbox();
setInterval(pollOutbox, WATCH_MS);   // COUNT 두 번이라 가볍다. 30초면 업로드 후 감소가 최대 60초 늦었다
boot().then(watchMes);
}
