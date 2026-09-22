/* ShiftLink PDA — 동작하는 프로토타입
 * ─────────────────────────────────────────────────────────────────────
 * 설계: docs/planning/PDA_카메라_설비식별_고도화.md
 * 구상: docs/design/pda_ui/pda_ui_mockup.html
 *
 * 지키는 규범
 *   C-102  검색 대상 = status=accepted AND split=kb AND grade=L1
 *   C-099  sealed 분할은 열지 않는다 — 파일 자체를 읽지 않음
 *   D-39   인식은 마커 디코딩(QR)만. 신경망 없음
 *   D-41   확정되지 않았거나 카탈로그에 없는 설비로는 검색하지 않는다
 *   D-42   원본 이미지는 단말 밖으로 나가지 않는다
 *   §5.3   QR 페이로드는 code(HPU-01). equipment_id(EQ-0001)가 아니다
 *   §9.2   QueryRequest.eq_id 에는 equipment_id 를 넣는다
 *   §6.1   신뢰도 대신 연속 프레임 일치 수(frame_votes)
 */
'use strict';

// ── 정본 경로 (저장소 루트 기준) ────────────────────────────────────
// dev(EV-0032)·sealed(EV-0033)는 읽지 않는다. 파일 단위 격리가 필터보다 확실하다.
const DATA_ROOT = '../../../data/';
/* main(#40)이 docs/data/ 를 재편했다. 새 경로를 먼저 시도하고 구 경로로 폴백한다
 * — 머지 전 트리와 머지 후 트리에서 모두 동작해야 하기 때문이다.
 * 머지가 끝나면 폴백(두 번째 항목)을 지운다. */
const SOURCES = {
  catalog: ['reference/00_plant_and_relations.json', '00_plant_and_relations.json'],
  kb: [
    ['knowledge_cards/01_kb_cards_shared.json', '01_kb_cards_shared.json'],
    ['scenarios/EV-0031_upstream_cause.json', 'EV-0031_upstream_cause.json']
  ]
};
const USED_PATHS = [];

const QR_PREFIX = 'SHIFTLINK:EQ:';
const VOTE_WINDOW = 3;
const MAX_ATTEMPTS = 3;
const FRAMES_PER_ATTEMPT = 12;
const SCAN_INTERVAL_MS = 120;
const API_TIMEOUT_MS = 8000;
const RECENT_MAX = 3;

const TYPE_COLOR = { HPU:'hpu', GR:'gr', RT:'rt', CV:'cv', PDP:'pdp', CAU:'cau' };
const TYPE_BAND = { HPU:'빨강', GR:'파랑', RT:'노랑', CV:'초록', PDP:'보라', CAU:'하늘' };
const SCOPE_RANK = { equipment:0, segment:1, line:2 };

// ── 상태 ───────────────────────────────────────────────────────────
const S = {
  screen:'boot', equipment:[], cards:[], handovers:[], groups:{}, types:{},
  eq:null, source:null, scanId:null, markerValue:null, frameVotes:0,
  symptom:null,   // { text, other:boolean } — 선택된 증상
  observations:[], recent:[], outbox:[], online:null, netNote:null,
  detector:null, stream:null, timer:null,
  votes:[], noneFrames:0, attempts:0, pending:null,
  scanStartedAt:0, lastScanMs:null, localScanSeq:0,
  waitAbort:false, ranked:null, tries:[], attemptSeq:0
};

const $ = (id) => document.getElementById(id);
const byType = (t) => TYPE_COLOR[t] ? 'var(--' + TYPE_COLOR[t] + ')' : 'var(--tx-3)';
const findByCode = (code) => S.equipment.find((e) => e.code === code) || null;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ── 부팅: 정본 적재 ────────────────────────────────────────────────
async function boot() {
  try {
    const cat = await fetchFirst(SOURCES.catalog);
    S.groups = {};
    (cat.equipment_groups || []).forEach((g) => { S.groups[g.equipment_group_id] = g; });
    S.types = {};
    (cat.equipment_types || []).forEach((t) => { S.types[t.equipment_type_id] = t; });
    S.equipment = (cat.equipment || []).map((e) => ({
      equipment_id: e.equipment_id,
      code: e.code,
      type: (S.types[e.equipment_type_id] || {}).type_code || '',
      group: (S.groups[e.equipment_group_id] || {}).name || '',
      where: e.location_text || '',
      signals: (e.measurement_points || []).map((m) => ({
        signal: m.signal, unit: m.unit,
        min: m.normal_min, max: m.normal_max,
        alarmLow: m.alarm_low, alarmHigh: m.alarm_high
      }))
    }));

    const all = [];
    for (const candidates of SOURCES.kb) {
      const d = await fetchFirst(candidates);
      (d.knowledge_cards || []).forEach((c) => all.push(c));
      (d.handover_records || []).forEach((h) => S.handovers.push(h));
    }
    // C-102 — 읽은 파일이 kb 전용이지만 방어적으로 한 번 더 거른다.
    S.cards = all.filter((c) =>
      c.status === 'accepted' && c.split === 'kb' && c.grade === 'L1');

    const dropped = all.length - S.cards.length;
    const legacy = USED_PATHS.filter((p) => p.indexOf('/') === -1).length;
    $('dData').textContent = '설비 ' + S.equipment.length + '대 · 카드 ' + S.cards.length + '장'
      + (dropped ? ' (비대상 ' + dropped + '장 제외)' : '') + ' · 인계 ' + S.handovers.length + '건'
      + (legacy ? ' · 구 경로 ' + legacy + '개 (main 머지 전)' : ' · 신 경로');

    if (!S.equipment.length || !S.cards.length) throw new Error('정본이 비어 있습니다');

    renderManualList();
    renderSimOptions();
    show('home');
  } catch (err) {
    $('bootMsg').textContent = '정본 데이터를 읽지 못했습니다.';
    const box = document.createElement('div');
    box.className = 'alert bad';
    box.innerHTML = '<p class="hd">데이터 로드 실패</p><p class="p"></p><code></code>'
      + '<p class="p">저장소 <b>루트</b>에서 서버를 띄워야 <code>docs/data/</code> 에 닿습니다.<br>'
      + '<code>python -m http.server 8791</code> → '
      + '<code>http://localhost:8791/docs/design/pda_ui/prototype/pda.html</code></p>';
    box.querySelector('.p').textContent = String(err && err.message || err);
    box.querySelector('code').textContent = new URL(DATA_ROOT, location.href).href;
    $('bootErr').appendChild(box);
  }
}

async function fetchJson(url) {
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error(url.split('/').pop() + ' — HTTP ' + res.status);
  return res.json();
}

/* 후보 경로를 순서대로 시도한다. 전부 실패하면 첫 후보 기준으로 오류를 낸다. */
async function fetchFirst(candidates) {
  let firstErr = null;
  for (const rel of candidates) {
    try {
      const data = await fetchJson(DATA_ROOT + rel);
      USED_PATHS.push(rel);
      return data;
    } catch (err) { if (!firstErr) firstErr = err; }
  }
  throw firstErr || new Error(candidates[0] + ' — 읽을 수 없음');
}

// ── 화면 전환 ──────────────────────────────────────────────────────
function show(name) {
  if (S.screen === 'scan' && name !== 'scan') stopCamera();
  S.screen = name;
  document.querySelectorAll('.screen').forEach((el) => {
    el.classList.toggle('on', el.id === 's-' + name);
  });
  const hideCtx = name === 'scan' || name === 'manual' || name === 'nocam' || name === 'boot';
  $('ctx').classList.toggle('on', !!S.eq && !hideCtx);
  $('net').hidden = (name === 'boot');
  const pane = document.querySelector('#s-' + name + ' .pane');
  if (pane) pane.scrollTop = 0;
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
  $('dServer').textContent = S.online === true ? '연결'
    : S.online === false ? (S.netNote || '끊김') : '미확인';
  $('dOutbox').textContent = S.outbox.length + '건';
}

async function api(path, init) {
  const ctrl = new AbortController();
  const to = setTimeout(() => ctrl.abort(), API_TIMEOUT_MS);
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
  S.eq = eq; S.source = source;
  S.scanId = (extra && extra.scanId) || null;
  S.markerValue = (extra && extra.markerValue) || null;
  S.frameVotes = (extra && extra.frameVotes) || 0;
  S.observations = []; S.ranked = null; S.tries = []; S.attemptSeq = 0; S.symptom = null;
  S.recent = [eq.code].concat(S.recent.filter((c) => c !== eq.code)).slice(0, RECENT_MAX);
  renderContext(); renderRecent(); renderObsSignals(); renderObsList();
  $('dSource').textContent = source + (S.scanId ? ' · ' + S.scanId : '');
}

function renderContext() {
  if (!S.eq) { $('ctx').classList.remove('on'); return; }
  $('ctxRail').style.background = byType(S.eq.type);
  $('ctxId').textContent = S.eq.code;
  $('ctxName').textContent = S.eq.group;
  const camera = S.source === 'camera_scan';
  const src = $('ctxSrc');
  src.classList.toggle('manual', !camera);
  src.textContent = (camera ? '✓ 카메라 확정' : '· 직접 선택')
    + (S.scanId ? ' · ' + S.scanId : '')
    + (camera && S.frameVotes ? ' · ' + S.frameVotes + '/' + VOTE_WINDOW + ' 프레임' : '');
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
function setScanState(kind, text, votes) {
  $('reticle').className = 'reticle' + (kind ? ' ' + kind : '');
  $('scanState').className = kind || '';
  $('scanText').textContent = text;
  const bar = $('voteBar');
  if (typeof votes === 'number' && votes > 0) {
    bar.hidden = false;
    [].forEach.call(bar.children, (el, i) => {
      el.className = 'vote' + (i < votes ? (votes >= VOTE_WINDOW ? ' on' : ' pend') : '');
    });
  } else bar.hidden = true;
}

function resetScanState() {
  S.votes = []; S.noneFrames = 0; S.attempts = 0; S.pending = null;
  S.scanStartedAt = Date.now();
  $('scanConfirm').hidden = true;
  setScanState('', '상자를 프레임 안에', 0);
}

async function startScan() {
  show('scan'); resetScanState();
  if (!window.isSecureContext || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia)
    return showNoCam('secure');
  if (!('BarcodeDetector' in window)) return showNoCam('detector');
  try { S.detector = new BarcodeDetector({ formats: ['qr_code'] }); }
  catch (_) { return showNoCam('detector'); }
  try {
    S.stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 } }, audio: false });
  } catch (err) {
    return showNoCam(err && err.name === 'NotAllowedError' ? 'permission' : 'device', err);
  }
  const v = $('video'); v.srcObject = S.stream;
  try { await v.play(); } catch (_) {}
  S.scanStartedAt = Date.now();
  S.timer = setInterval(tick, SCAN_INTERVAL_MS);
}

function stopCamera() {
  if (S.timer) { clearInterval(S.timer); S.timer = null; }
  if (S.stream) { S.stream.getTracks().forEach((t) => t.stop()); S.stream = null; }
  const v = $('video'); if (v) v.srcObject = null;
}

async function tick() {
  const v = $('video');
  if (!S.detector || !v || v.readyState < 2) return;
  let codes = [];
  try { codes = await S.detector.detect(v); } catch (_) { return; }
  feed(codes.map((c) => c.rawValue));
}

/* 디코딩 원문 → 판정. 진단 패널 주입도 같은 경로를 쓴다. */
function feed(rawValues) {
  let hit = null;
  for (const raw of rawValues || []) {
    const text = String(raw).trim();
    if (text.indexOf(QR_PREFIX) !== 0) continue;      // 접두어 검사 = 1차 방어
    const eq = findByCode(text.slice(QR_PREFIX.length)); // code → 카탈로그 = 2차 방어
    if (!eq) continue;
    hit = { eq: eq, marker: text }; break;
  }
  if (!hit) {
    S.noneFrames += 1;
    if (S.noneFrames >= FRAMES_PER_ATTEMPT) {
      S.noneFrames = 0; S.attempts += 1;
      if (S.attempts >= MAX_ATTEMPTS) return failScan();
      setScanState('', '인식 안 됨 — 각도를 바꿔 보세요 (' + S.attempts + '/' + MAX_ATTEMPTS + ')', 0);
    }
    return;
  }
  S.noneFrames = 0;
  S.votes.push(hit);
  if (S.votes.length > VOTE_WINDOW) S.votes.shift();
  const codes = S.votes.map((x) => x.eq.code);
  const top = codes[codes.length - 1];
  const agree = codes.filter((c) => c === top).length;
  if (agree >= VOTE_WINDOW) return lockScan(hit, VOTE_WINDOW);
  if (agree === 2 && S.votes.length >= VOTE_WINDOW) return askConfirm(hit, 2);
  haptic(30);
  setScanState('candidate', hit.eq.code + ' 확인 중…', agree);
}

function askConfirm(hit, votes) {
  S.pending = { hit: hit, votes: votes };
  haptic(30);
  setScanState('candidate', hit.eq.code + ' — 맞으면 확인을 누르세요', votes);
  $('scanConfirm').hidden = false;
}

function lockScan(hit, votes) {
  if (S.timer) { clearInterval(S.timer); S.timer = null; }
  S.lastScanMs = Date.now() - S.scanStartedAt;
  $('dScan').textContent = hit.eq.code + ' · ' + votes + '/' + VOTE_WINDOW + ' · '
    + S.lastScanMs + 'ms' + (S.lastScanMs < 1000 ? ' (목표 충족)' : ' (목표 1000ms 초과)');
  haptic([120]);
  setScanState('locked', hit.eq.code + ' 확정', votes);
  $('scanConfirm').hidden = true;
  confirmScan(hit, votes);
}

function failScan() {
  if (S.timer) { clearInterval(S.timer); S.timer = null; }
  haptic([30, 60, 30]);
  setScanState('failed', '인식 실패 — 직접 선택', 0);
  setTimeout(() => { if (S.screen === 'scan') openManual(); }, 900);
}

function localScanId() {
  S.localScanSeq += 1;
  return 'SC-LOCAL-' + String(S.localScanSeq).padStart(4, '0');
}

async function confirmScan(hit, votes) {
  const payload = {
    equipment_id: hit.eq.equipment_id,   // 정본 키 — 서버·질의는 이 값
    code: hit.eq.code,                   // 인쇄 라벨과 같은 표시값
    method: 'qr',
    marker_value: hit.marker,            // 디코딩 원문. 이미지는 보내지 않는다(D-42)
    frame_votes: votes
  };
  let scanId = null;
  try {
    const res = await api('/api/equipment/scan', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload) });
    if (res.status === 404) {
      setScanState('failed', '서버가 이 설비를 모릅니다 — 확정 취소', 0);
      haptic([30, 60, 30]);
      setTimeout(() => { if (S.screen === 'scan') openManual(); }, 1200);
      return;
    }
    if (res.ok) {
      const body = await res.json().catch(() => ({}));
      scanId = body.scan_id || null;
    } else { scanId = localScanId(); S.outbox.push(payload); renderNet(); }
  } catch (_) {
    scanId = localScanId(); S.outbox.push(payload); renderNet();
  }
  setContext(hit.eq, 'camera_scan', { scanId: scanId, markerValue: hit.marker, frameVotes: votes });
  setTimeout(() => { if (S.screen === 'scan') show('ctx'); }, 420);
}

function showNoCam(reason, err) {
  stopCamera();
  const box = $('nocamBox'), why = $('nocamWhy'), fix = $('nocamFix'), a = $('nocamAddr');
  box.className = 'alert bad'; a.hidden = false;
  a.textContent = location.origin + location.pathname;
  if (reason === 'secure') {
    why.textContent = '보안 컨텍스트가 아닙니다. 카메라는 HTTPS 또는 localhost에서만 열립니다.';
    fix.textContent = '→ https:// 주소로 접속하세요. 자체 서명 인증서를 이 단말에 먼저 신뢰 등록해야 합니다.';
  } else if (reason === 'detector') {
    box.className = 'alert';
    why.textContent = '이 브라우저는 QR 디코딩(BarcodeDetector)을 지원하지 않습니다. ArUco 경로는 아직 구현 범위가 아닙니다(U-9 미결).';
    fix.textContent = '→ 직접 선택으로 계속하세요. 지원 브라우저는 Chrome 계열입니다.';
  } else if (reason === 'permission') {
    why.textContent = '카메라 권한이 거부되어 있습니다.';
    fix.textContent = '→ 주소창의 자물쇠 아이콘에서 카메라를 허용한 뒤 다시 시도하세요.';
  } else {
    why.textContent = '카메라 장치를 열 수 없습니다.' + (err && err.name ? ' (' + err.name + ')' : '');
    fix.textContent = '→ 다른 앱이 카메라를 쓰고 있지 않은지 확인하세요.';
  }
  show('nocam');
}

// ── 직접 선택 ──────────────────────────────────────────────────────
function renderManualList() {
  const list = $('manualList'); list.innerHTML = '';
  S.equipment.forEach((eq) => {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'row';
    b.innerHTML = '<i class="rail"></i><span class="txt"><span class="id"></span><br>'
      + '<span class="nm"></span></span><span class="mk"></span>';
    b.querySelector('.rail').style.background = byType(eq.type);
    b.querySelector('.id').textContent = eq.code;
    b.querySelector('.nm').textContent = eq.group + ' · ' + eq.where;
    b.querySelector('.mk').textContent = TYPE_BAND[eq.type] || '';
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
    o.value = s.signal; o.textContent = s.signal + ' (' + s.unit + ')';
    sel.appendChild(o);
  });
  renderObsRange();
}
function renderObsRange() {
  const s = (S.eq && S.eq.signals.find((x) => x.signal === $('obsSignal').value)) || null;
  $('obsRange').textContent = s
    ? '정상 범위 ' + fmt(s.min) + '~' + fmt(s.max) + ' ' + s.unit
      + (s.alarmHigh != null ? ' · 경보 ' + fmt(s.alarmHigh) + ' 이상' : '')
      + (s.alarmLow != null ? ' · 경보 ' + fmt(s.alarmLow) + ' 이하' : '')
    : '';
}
const fmt = (v) => (v == null ? '—' : String(v));

function renderObsList() {
  const box = $('obsList'); box.innerHTML = '';
  S.observations.forEach((o, i) => {
    const row = document.createElement('div');
    row.className = 'obs';
    row.innerHTML = '<span class="mono"></span><button class="x" type="button" aria-label="삭제">✕</button>';
    row.querySelector('.mono').textContent = o.signal + ' = ' + o.value + ' ' + o.unit;
    row.querySelector('.x').addEventListener('click', () => {
      S.observations.splice(i, 1); renderObsList();
    });
    box.appendChild(row);
  });
}

// ── 증상 선택 ──────────────────────────────────────────────────────
/* 목록은 해당 설비 카드의 `symptom` 필드에서 나온다. 지어내지 않는다.
 * 「기타」를 목록 항목과 같은 크기·같은 자리에 두는 이유 — 목록에서만 고를 수
 * 있으면 항상 무언가 찾히고 「해당 지식 없음」이 영영 나오지 않는다. 그 화면은
 * 이 시스템에서 실패가 아니라 기능이므로 도달 경로를 좁히면 안 된다. */
function symptomsFor(eq) {
  const out = [];
  S.cards.forEach((c) => {
    if ((c.equipment_ids || []).indexOf(eq.equipment_id) === -1) return;
    const s = (c.symptom || '').trim();
    if (s && out.indexOf(s) === -1) out.push(s);
  });
  return out;
}

/* 선택된 증상 문자열. 계약(QueryRequest.question)은 그대로 문자열 하나다. */
function currentQuestion() {
  if (!S.symptom) return '';
  return S.symptom.other ? $('question').value.trim() : S.symptom.text;
}

function renderSymptoms() {
  const list = $('symptomList');
  list.innerHTML = '';
  // 「기타」가 선택된 상태에서만 입력창을 띄운다. 선택을 바꾸거나 비우면 내용도 지운다.
  const other = !!(S.symptom && S.symptom.other);
  $('otherWrap').hidden = !other;
  if (!other) $('question').value = '';
  if (!S.eq) return;
  const items = symptomsFor(S.eq);

  if (!items.length) {
    const p = document.createElement('p');
    p.className = 'hint';
    p.textContent = '이 설비에 등록된 증상이 없습니다. 아래에서 직접 적어 주세요.';
    list.appendChild(p);
  }

  const mk = (text, other) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'row sym' + (other ? ' other' : '');
    b.innerHTML = '<span class="mark">○</span><span class="txt"></span>';
    b.querySelector('.txt').textContent = text;
    b.addEventListener('click', () => {
      S.symptom = { text: other ? '' : text, other: !!other };
      renderSymptoms();
      if (other) setTimeout(() => $('question').focus(), 0);
      haptic(20);
      renderAskBlock();
    });
    const sel = !!S.symptom && (other ? S.symptom.other : (!S.symptom.other && S.symptom.text === text));
    if (sel) { b.classList.add('sel'); b.querySelector('.mark').textContent = '●'; }
    list.appendChild(b);
  };

  items.forEach((s) => mk(s, false));
  mk('기타 — 직접 입력', true);      // 목록과 같은 크기·같은 자리
}

// ── 조건 평가 ──────────────────────────────────────────────────────
function cmp(op, a, b) {
  switch (op) {
    case 'gte': return a >= b; case 'gt': return a > b;
    case 'lte': return a <= b; case 'lt': return a < b;
    case 'eq': return a === b;
    case 'in': return Array.isArray(b) && b.indexOf(a) !== -1;
    default: return false;
  }
}
const OPTXT = { gte:'≥', gt:'>', lte:'≤', lt:'<', eq:'=' };

/* 관측값이 없으면 "일치"로 속이지 않고 미평가로 남긴다. */
function evalCondition(c) {
  const obs = S.observations.find((o) => o.signal === c.signal);
  if (!obs) return { state:'unknown', text: c.signal + ' — 관측값 없음' };
  const ok = cmp(c.op, obs.value, c.value);
  const sym = OPTXT[c.op] || c.op;
  return {
    state: ok ? 'match' : 'miss',
    text: c.signal + ' ' + obs.value + ' ' + sym + ' ' + c.value + ' · ' + (ok ? '일치' : '불일치')
  };
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

function rankCards(eq) {
  const hits = S.cards.filter((c) => (c.equipment_ids || []).indexOf(eq.equipment_id) !== -1);
  const safety = hits.filter((c) => c.safety_flag === true);
  const rest = hits.filter((c) => c.safety_flag !== true);

  const scored = rest.map((c) => {
    const conds = (c.conditions || []).map(evalCondition);
    const anyMiss = conds.some((x) => x.state === 'miss');
    const anyMatch = conds.some((x) => x.state === 'match');
    const direct = c.scope_level === 'equipment';
    const scope = SCOPE_RANK[c.scope_level] != null ? SCOPE_RANK[c.scope_level] : 3;
    const reasons = [];
    if (anyMatch) reasons.push('조건 일치');
    if (direct) reasons.push('설비 직접 지정');
    if (!anyMatch && !anyMiss && conds.length) reasons.push('조건 미평가');
    if (scope >= 2) reasons.push('범위 넓음 (line)');
    else if (scope === 1 && !direct) reasons.push('범위 중간 (segment)');
    if (!reasons.length) reasons.push('설비 관련');
    return {
      card: c, conds: conds, excluded: anyMiss,
      why: reasons.join(' · '),
      key: [anyMatch ? 0 : 1, direct ? 0 : 1, scope]
    };
  });

  const applicable = scored.filter((x) => !x.excluded)
    .sort((a, b) => a.key[0] - b.key[0] || a.key[1] - b.key[1] || a.key[2] - b.key[2]);
  const excluded = scored.filter((x) => x.excluded);
  return { safety: safety, actions: applicable, excluded: excluded, total: hits.length };
}

// ── 렌더 ───────────────────────────────────────────────────────────
function safetyEl(c, pin) {
  const d = document.createElement('div');
  d.className = 'safety' + (pin ? ' pin' : '');
  d.innerHTML = '<div class="hd"><span class="dot"></span><span>안전 · 조치 전 필수</span>'
    + (pin ? '<span class="pinbadge">고정</span>' : '') + '</div>'
    + '<div class="kid"></div><div class="ttl"></div><p class="body" style="margin:0"></p>'
    + '<p class="basis" style="margin:0"></p>'
    + (pin ? '<div class="gate">아래 조치는 이 조건을 지킨 상태에서만 수행한다</div>' : '');
  d.querySelector('.kid').textContent = c.card_id + ' · ' + c.tacit_type + ' · ' + c.grade;
  d.querySelector('.ttl').textContent = c.title;
  d.querySelector('.body').textContent = c.know_how;
  d.querySelector('.basis').textContent = '근거 — ' + (c.safety_basis || '근거 미기재');
  return d;
}

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
  why.className = 'why' + (item.excluded ? ' no' : (rank === 1 ? '' : ' dim'));
  why.textContent = item.excluded ? '조건 불일치 — 이 카드는 지금 쓰면 안 된다' : item.why;
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

  // T3 는 저장된 ①②③ 순서를 그대로 유지한다(D-28).
  const parts = String(c.know_how).split(/(?=[①②③④⑤⑥⑦⑧⑨])/).filter((x) => x.trim());
  if (c.tacit_type === 'T3' && parts.length > 1) {
    const ol = document.createElement('ol'); ol.className = 'steps';
    parts.forEach((p) => {
      const t = p.trim();
      const li = document.createElement('li');
      li.innerHTML = '<span class="st"></span><span class="tx"></span>';
      li.querySelector('.st').textContent = t.slice(0, 1);
      li.querySelector('.tx').textContent = t.slice(1).trim();
      ol.appendChild(li);
    });
    d.appendChild(ol);
  } else {
    const b = document.createElement('p');
    b.className = 'body'; b.style.margin = '0'; b.textContent = c.know_how;
    d.appendChild(b);
  }

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
    btn.type = 'button'; btn.className = 'btn sm';
    btn.textContent = '이 조치 시도';
    btn.addEventListener('click', () => recordTry(c));
    d.appendChild(btn);
  }
  return d;
}

function renderResult() {
  const pane = $('resultPane'); pane.innerHTML = '';
  const r = S.ranked;
  r.safety.forEach((c) => pane.appendChild(safetyEl(c, true)));

  const triedIds = S.tries.map((t) => t.card_id);
  const remaining = r.actions.filter((x) => triedIds.indexOf(x.card.card_id) === -1);

  const lbl = document.createElement('p');
  lbl.className = 'lbl hot';
  lbl.textContent = '조치 — 관련도 순 ' + remaining.length + '건 (검색 대상 카드 기준)';
  pane.appendChild(lbl);

  if (!remaining.length) {
    const d = document.createElement('div');
    d.className = 'try now';
    d.innerHTML = '<div class="hd"><span class="rkno next">—</span>'
      + '<span class="aid">조치 후보 소진</span>'
      + '<span class="pill" style="margin-left:auto">인계 권장</span></div>'
      + '<div class="fld"><span class="k">상태</span><span class="v"></span></div>';
    d.querySelector('.v').textContent = S.eq.code + '에 적용 가능한 조치를 모두 시도했습니다. '
      + '남은 원인은 등록된 지식 밖입니다.';
    pane.appendChild(d);
  }
  remaining.forEach((x, i) => pane.appendChild(actionEl(x, i + 1)));

  if (r.excluded.length) {
    const l2 = document.createElement('p');
    l2.className = 'lbl';
    l2.textContent = '적용 안 됨 ' + r.excluded.length + '건 — 이유와 함께 남김';
    pane.appendChild(l2);
    r.excluded.forEach((x) => {
      const el = actionEl(x, null); el.classList.add('out'); pane.appendChild(el);
    });
  }

  if (S.tries.length) {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'btn sm ghost';
    b.textContent = '시도 기록 보기 (' + S.tries.length + '건)';
    b.addEventListener('click', () => renderTries());
    pane.appendChild(b);
  }
}

// ── 시도 기록 ──────────────────────────────────────────────────────
function recordTry(card) {
  S.attemptSeq += 1;
  const id = 'AT-' + String(S.attemptSeq).padStart(4, '0');
  const observed = S.observations.length
    ? S.observations.map((o) => o.signal + ' ' + o.value + ' ' + o.unit).join(', ')
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
  if (r && r.safety.length) pane.appendChild(safetyEl(r.safety[0], true));

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
    if (next.length) { renderResult(); show('result'); }
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

// ── 검색 실행 ──────────────────────────────────────────────────────
function searchBlockedReason() {
  if (!S.eq || !S.source) return '설비가 확정되지 않았습니다. 먼저 스캔하거나 직접 선택하세요.';
  if (!findByCode(S.eq.code)) return '카탈로그에 없는 설비입니다.';
  if (!S.symptom) return '증상을 선택하세요.';
  if (S.symptom.other && !$('question').value.trim()) return '증상을 직접 적어 주세요.';
  return null;
}
function renderAskBlock() {
  const why = searchBlockedReason();
  $('askBlock').hidden = !why;
  $('askBlockWhy').textContent = why || '';
  $('doSearch').disabled = !!why;
}

function setStep(id, pct, state) {
  const el = $(id);
  el.className = 'pstep' + (state ? ' ' + state : '');
  el.querySelector('.bar i').style.width = pct + '%';
  el.querySelector('.mk').textContent = state === 'done' ? '✓' : state === 'run' ? '⟳' : '·';
}

async function runSearch() {
  if (searchBlockedReason()) { renderAskBlock(); return; }
  S.waitAbort = false; S.tries = []; S.attemptSeq = 0;
  show('wait');
  $('waitCards').innerHTML = ''; $('waitLbl').hidden = true;
  setStep('st1', 0, 'run'); setStep('st2', 0, ''); setStep('st3', 0, '');

  if (window.console) console.log('[pda] query', queryPayload());
  const r = rankCards(S.eq);
  S.ranked = r;

  await sleep(700);
  if (S.waitAbort) return;
  setStep('st1', 100, 'done');

  // 안전 카드는 생성을 기다릴 이유가 없다 — 검색되는 즉시 올린다.
  if (r.safety.length) {
    $('waitLbl').hidden = false;
    r.safety.forEach((c) => $('waitCards').appendChild(safetyEl(c, false)));
  }

  setStep('st2', 0, 'run');
  for (let p = 0; p <= 100; p += 25) { await sleep(160); if (S.waitAbort) return; setStep('st2', p, 'run'); }
  setStep('st2', 100, 'done');

  // 실측 p95 21~34초 구간. 프로토타입에서는 3초로 축약한다.
  setStep('st3', 0, 'run');
  for (let p = 0; p <= 100; p += 10) { await sleep(300); if (S.waitAbort) return; setStep('st3', p, 'run'); }
  setStep('st3', 100, 'done');
  if (S.waitAbort) return;

  if (!r.total) { show('empty'); return; }
  if (r.safety.length) haptic([120]);
  renderResult(); show('result');
}

// ── 인계 ───────────────────────────────────────────────────────────
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

    const open = (h.open_items || []).filter((it) => it.status !== 'closed');
    const l2 = document.createElement('p');
    l2.className = 'lbl'; l2.textContent = '미종료 ' + open.length + '건';
    pane.appendChild(l2);

    open.forEach((it) => {
      const d = document.createElement('div');
      d.className = 'card';
      d.innerHTML = '<div class="pills"><span class="pill miss st"></span>'
        + '<span class="pill du"></span></div>'
        + '<p class="body" style="margin:0"></p><div class="src"></div>';
      const st = d.querySelector('.st');
      st.textContent = it.status;
      if (it.status !== 'open') st.className = 'pill unknown st';
      d.querySelector('.du').textContent = it.due_shift + '조 마감';
      d.querySelector('.body').textContent = it.text;
      d.querySelector('.src').textContent = '근거 ' + (it.basis_ids || []).join(' · ');
      pane.appendChild(d);
    });
  });
  show('handover');
}

function openHandoverNew() {
  const ctx = S.tries.length
    ? '시도 ' + S.tries.length + '건 실패 (' + S.tries.map((t) => t.attempt_id).join(' · ') + ')'
      + (S.observations.length ? ' · ' + S.observations.map((o) => o.signal + ' ' + o.value).join(', ') : '')
    : (S.observations.length
        ? S.observations.map((o) => o.signal + ' ' + o.value + ' ' + o.unit).join(', ')
        : '시도 기록 없음 — 직접 입력 필요');
  $('hoCtx').textContent = ctx;
  validateHandover();
  show('hoNew');
}

function validateHandover() {
  const ok = ['hoRole', 'hoTiming', 'hoChannel', 'hoAck'].every((id) => $(id).value.trim());
  $('hoSave').disabled = !ok;
  $('hoWarn').hidden = ok;
}

// ── 진단 ───────────────────────────────────────────────────────────
function renderSimOptions() {
  const sel = $('simValue'); sel.innerHTML = '';
  S.equipment.forEach((e) => {
    const o = document.createElement('option');
    o.value = QR_PREFIX + e.code;
    o.textContent = QR_PREFIX + e.code;
    sel.appendChild(o);
  });
  const bad = document.createElement('option');
  bad.value = '1Z999AA10123456784';
  bad.textContent = '1Z999AA10123456784 (잡 QR — 무시되어야 함)';
  sel.appendChild(bad);
  const unknown = document.createElement('option');
  unknown.value = QR_PREFIX + 'HPU-99';
  unknown.textContent = QR_PREFIX + 'HPU-99 (미등록 — 무시되어야 함)';
  sel.appendChild(unknown);
}

// ── 배선 ───────────────────────────────────────────────────────────
function on(id, fn) { const el = $(id); if (el) el.addEventListener('click', fn); }

on('toScan', startScan);
on('scanClose', () => show('home'));
on('scanManual', openManual);
on('scanConfirm', () => { if (S.pending) lockScan(S.pending.hit, S.pending.votes); });
on('toManual', openManual);
on('manualClose', () => show(S.eq ? 'ctx' : 'home'));
on('manualToScan', startScan);
on('nocamClose', () => show('home'));
on('nocamManual', openManual);
on('nocamRetry', startScan);
on('ctxBack', () => show('home'));
on('ctxEdit', startScan);
on('toAsk', () => { renderSymptoms(); renderObsList(); renderAskBlock(); show('ask'); });
on('askBack', () => show('ctx'));
on('doSearch', runSearch);
on('waitCancel', () => { S.waitAbort = true; show('ask'); });
on('resultBack', () => show('ctx'));
on('triesBack', () => { renderResult(); show('result'); });
on('emptyBack', () => show('ctx'));
on('emptyRetry', () => { renderSymptoms(); renderAskBlock(); show('ask'); });
on('toHandover', openHandover);
on('toHandoverHome', openHandover);
on('hoBack', () => show(S.eq ? 'ctx' : 'home'));
on('toHandoverNew', openHandoverNew);
on('hoNewBack', () => show('ctx'));
on('hoSave', () => {
  haptic([120]);
  $('hoWarn').hidden = false;
  $('hoWarn').innerHTML = '<p class="p">저장됨 (프로토타입 — 서버 전송 없음). '
    + 'REQUIRED_CONTEXT 에 시도 기록이 자동으로 들어갔습니다.</p>';
});
['hoRole','hoTiming','hoChannel','hoAck'].forEach((id) => {
  $(id).addEventListener('input', validateHandover);
});

$('question').addEventListener('input', renderAskBlock);
$('obsSignal').addEventListener('change', renderObsRange);
on('obsAdd', () => {
  const sel = $('obsSignal'), val = $('obsValue');
  if (!sel.value || val.value === '') return;
  const meta = S.eq.signals.find((x) => x.signal === sel.value) || { unit: '' };
  S.observations.push({ signal: sel.value, unit: meta.unit, value: Number(val.value) });
  val.value = ''; renderObsList();
});

on('toDiag', () => $('diag').classList.toggle('on'));
on('simFeed', () => {
  if (S.screen !== 'scan') { show('scan'); resetScanState(); }
  feed([$('simValue').value]);
});

// ── 기동 ───────────────────────────────────────────────────────────
$('dSecure').textContent = window.isSecureContext
  ? '보안 컨텍스트 (' + location.protocol + ')'
  : '아님 (' + location.protocol + ') — 카메라 열리지 않음';
$('dDetector').textContent = ('BarcodeDetector' in window) ? '지원' : '미지원 — 수동 선택 경로만';
renderNet();
probeServer();
boot();
