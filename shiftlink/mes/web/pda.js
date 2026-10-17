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
const RECENT_MAX = 8;

const TYPE_COLOR = { HPU:'hpu', GR:'gr', RT:'rt', CV:'cv', PDP:'pdp', CAU:'cau' };

// ── 상태 ───────────────────────────────────────────────────────────
const S = {
  screen:'boot', equipment:[], cards:[], handovers:[], basisRecords:{}, groups:{}, types:{},
  eq:null, source:null, scanId:null,
  chat:[], chatSeq:0,   // 증상 질의 대화. 한 턴 = /api/query 한 번 — 이전 턴은 서버로 보내지 않는다
  observations:[], obsRemoved:[], recent:[], outbox:[], online:null, netNote:null,
  scanRun:0, scanStartedAt:0, mes:null, mesExcluded:[],
  waitAbort:false, ranked:null, tries:[], attemptSeq:0,
  operator:null, linkedEquipment:null, chatHidden:false, reportSelected:[], reportFilter:'all', savedHandovers:[], reportDraftLoaded:false,
  foldOpen:{}   // 정상값 접기 펼침 상태(목록별) — 3초 갱신으로 다시 그려도 유지
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
/* 화면용 짧은 이름. 구성(MES)의 name 은 그대로 둔다. */
const SHORT_NAMES = {
  '동일 조건 정상 대비 아이들러 회전 비율': '아이들러 회전 비율', '컨베이어 구동부 진동 RMS': '구동부 진동 RMS',
  '컨베이어 모터 전류': '모터 전류', '컨베이어 속도': '벨트 속도',
  '리턴 라인 유면 아래 잠김 깊이': '리턴 라인 잠김 깊이', '유면과 흡입 위치 높이차': '흡입 높이차',
  '냉각기 통과 오일 유량': '냉각기 오일 유량', '축압기 가스측 운전 압력': '축압기 가스 압력', '축압기 유체측 압력': '축압기 유체 압력',
  '감속기 오일 수분 함량': '오일 수분', '감속기 베어링 온도': '베어링 온도', '감속기 구동 전류': '구동 전류',
  '감속기 오일 레벨': '오일 레벨', '감속기 표면 온도': '표면 온도', '감속기 회전속도': '회전속도', '감속기 진동 RMS': '진동 RMS',
  '공기분사기 유출 압력': '분사기 압력', '차단기 L1극 표면 온도': 'L1극 온도', '차단기 L2극 표면 온도': 'L2극 온도', '차단기 L3극 표면 온도': 'L3극 온도'
};
const shortName = (n) => { const s = String(n || '').split(' (')[0]; return SHORT_NAMES[s] || s; };
/* 신호 ID 대신 MES 구성의 한글 이름. 파생 <signal>_state 는 "이름 상태". */
function signalName(sig) {
  const base = String(sig).replace(/_state$/, '');
  const spec = S.eq && S.eq.signals.find((x) => x.signal === base);
  const name = spec ? shortName(spec.name || base) : base;
  return base !== sig ? name + ' 상태' : name;
}
/* 서버·카드 원문의 단위·신호 ID를 화면용으로(질의에는 원문을 그대로 보낸다). */
const plain = (t) => String(t == null ? '' : t).replace(/\bdegC\b/g, '℃').replace(/\b(mm_s|m_min|L_min)\b/g, (u) => UNIT_TEXT[u]).replace(/(\d)\s*pct\b/g, '$1%')
  .replace(/\b[a-z]{2,}(?:_[a-z0-9]+)+\b/g, (id) => (S.eq && S.eq.signals.some((x) => x.signal === id.replace(/_state$/, '')) ? signalName(id) : id));
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

let afterBoot = () => show('account');   // 문서 블록이 로그인 기억(sessionStorage)으로 바꾼다

async function boot() {
  if (typeof document !== 'undefined') $('bootErr').innerHTML = '';
  try {
    const [cfg, cat, kb] = await Promise.all([getJson('/api/config'), getJson('/api/catalog'), getJson('/api/kb/cards')]);
    S.equipment = equipmentFrom(cfg.config, cat.data);
    S.cards = kb.cards || [];
    S.handovers = kb.handovers || [];
    S.basisRecords = kb.basis_records || {};

    if (!S.equipment.length || !S.cards.length) throw new Error('구성 또는 카드가 비어 있습니다');

    try { S.recent=JSON.parse(localStorage.getItem('shiftlink.recent')||'[]').filter((code)=>findByCode(code)); } catch (_) { S.recent=[]; }
    renderManualList();
    if (typeof document !== 'undefined') { renderRecent();renderHome();refreshSavedHandovers(); }
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

const navigationStack = [];
let navigatingBack = false;
function goBack() {
  const target = navigationStack.pop() || (S.operator ? 'home' : 'account');
  navigatingBack = true;
  try { if (target === 'scan') startScan(); else show(target); }
  finally { navigatingBack = false; }
}
function show(name) {
  if (name === 'login') name = 'account';
  if (name === 'chat') { S.chatHidden=false; name='ctx'; }
  if (S.screen === 'scan' && name !== 'scan') { S.scanRun+=1; stopUnityCamera(); }
  if (S.screen === 'face' && name !== 'face') stopFaceCamera();
  if (name !== S.screen && !navigatingBack) {
    if (['home','account','boot'].includes(name)) navigationStack.length=0;
    else if (S.screen && S.screen !== 'boot') navigationStack.push(S.screen);
  }
  S.screen=name;
  document.querySelectorAll('.screen').forEach((el)=>el.classList.toggle('on',el.id==='s-'+name));
  $('ctx').classList.toggle('on',!!S.eq&&['ctx','tries','hoNew','resolve'].includes(name));
  const signedOut=['boot','login','account','faceSetup','face'].includes(name);
  $('globalHeader').hidden=signedOut||['scan','handover','dutyDetail'].includes(name);$('net').hidden=signedOut;
  const back = $('navigationBack');
  back.hidden=['boot','account','login','home'].includes(name);
  document.querySelectorAll('.navigation-host').forEach(el=>el.classList.remove('navigation-host'));
  const backHost = $('globalHeader').hidden
    ? document.querySelector('#s-'+name+' > #scanState, #s-'+name+' > #faceState') || document.querySelector('#s-'+name+' > .appbar')
    : $('globalHeader');
  if (backHost && !back.hidden) {
    backHost.prepend(back);
    if (backHost !== $('globalHeader')) backHost.classList.add('navigation-host');
  }
  [['toScan','scan'],['toManual','manual']].forEach(([id,screen])=>{$(id).classList.toggle('active',name===screen);$(id).setAttribute('aria-current',name===screen?'page':'false');});
  $('notifyFloatWrap').hidden=signedOut||!$('globalHeader').hidden;$('notifyPanel').hidden=true;document.querySelectorAll('.notify').forEach((btn)=>btn.setAttribute('aria-expanded','false'));
  const pane=document.querySelector('#s-'+name+' .pane');if(pane)pane.scrollTop=0;
  document.documentElement.scrollTop=0;document.body.scrollTop=0;
  if(name==='home')renderHome();
  if(name==='ctx'&&S.eq){
    $('workEquipment').textContent=S.eq.code+' · '+S.eq.group;
    if(S.sensorsOpen===undefined)S.sensorsOpen=(S.faults||[]).some(f=>f.eq.equipment_id===S.eq.equipment_id);
    $('equipmentWorkspace').classList.toggle('sensors-open',!!S.sensorsOpen);
    $('toggleChat').textContent=S.sensorsOpen?'센서값 닫기':'센서값 열기';$('toggleChat').setAttribute('aria-expanded',String(!!S.sensorsOpen));
    renderMesStatus();renderChat();renderSymptoms();renderAskBlock();renderEquipmentMetrics();
  }
}

function haptic(p) { if (typeof navigator !== 'undefined' && navigator.vibrate) { try { navigator.vibrate(p); } catch (_) {} } }

// ── 네트워크 ───────────────────────────────────────────────────────
function renderNet() {
  const el = $('net');
  el.classList.toggle('ok', S.online === true);
  el.classList.toggle('warn', S.online === false);
  $('netText').textContent =
    S.online === true ? '연결 상태 · 정상' :
    S.online === false ? (S.netNote || '연결 상태 · 연결 끊김') : '연결 상태 · 확인 중…';
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
  S.sensorsOpen=(S.faults||[]).some(f=>f.eq.equipment_id===eq.equipment_id);S.sensorWasBad=false;
  S.scanId = (extra && extra.scanId) || null;
  S.observations = []; S.obsRemoved = []; S.ranked = null; S.tries = []; S.attemptSeq = 0; S.chat = [];
  S.safetyView = null; S.safetyOpen = false;
  S.mes = null; S.mesExcluded = []; S.sensorSnapshot = null;
  S.recent = [eq.code].concat(S.recent.filter((c) => c !== eq.code)).slice(0, RECENT_MAX);
  try { localStorage.setItem('shiftlink.recent',JSON.stringify(S.recent)); } catch (_) {}
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
  // 이 설비가 적힌 미완료 인계 항목 수 — 인계 확인 화면(openHandover)과 같은 기준
  const open = S.handovers.flatMap((h) => h.open_items || [])
    .filter((it) => String(it.text).includes(S.eq.code) && !['closed', 'done', 'withdrawn'].includes(it.status)).length;
  $('ctxHoNote').textContent = open ? '이 설비 처리·재확인 필요 ' + open + '건' : '이 설비의 남은 인계 항목 없음';
  $('toHandover').classList.toggle('warn', open > 0);
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

let unityCameraAbort = null;
function stopUnityCamera() {
  if (unityCameraAbort) unityCameraAbort.abort();
  unityCameraAbort = null;
  if (typeof document !== 'undefined') {
    const image = $('unityCamera');
    if (image) { image.onload = null; image.onerror = null; image.hidden = true; image.removeAttribute('src'); }
  }
}

const unityCameraHint = () => $('scanShoot').disabled ? 'Unity 가상 카메라 · 실시간 영상' : 'Unity 가상 카메라 · 설비를 화면 가운데 담고 「촬영」';

async function streamUnityCamera(run) {
  stopUnityCamera();
  const ctrl = new AbortController(); unityCameraAbort = ctrl;
  const image = $('unityCamera');
  let failed = false, openedAt = 0;
  const open = () => {
    failed = false; openedAt = Date.now();
    image.src = '/api/unity/stream?run=' + run + '&t=' + openedAt;
  };
  image.onload = () => {
    if (S.scanRun !== run || ctrl.signal.aborted) return;
    image.hidden = false;
    setScanState('', unityCameraHint());
  };
  image.onerror = () => { failed = true; image.hidden = true; };
  open();
  while (S.scanRun === run && S.screen === 'scan') {
    try {
      const res = await fetch('/api/unity/config', {cache:'no-store', signal:AbortSignal.any([ctrl.signal, AbortSignal.timeout(2500)])});
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const camera = await res.json();
      if (S.scanRun !== run || ctrl.signal.aborted) return;
      if (camera.stream_live && image.hidden) {  // 매번 쓰면 촬영 결과·확정 문구를 덮는다
        image.hidden = false;
        setScanState('', unityCameraHint());
      }
      if (failed || (!camera.stream_live && Date.now() - openedAt > 3500)) throw new Error('Camera disconnected');
    } catch (err) {
      if (ctrl.signal.aborted || S.scanRun !== run) return;
      image.hidden = true; image.removeAttribute('src');
      setScanState('failed', 'Unity 카메라 연결 대기 · 자동 재연결 중');
      await sleep(1000);
      if (S.scanRun !== run || ctrl.signal.aborted) return;
      open();
    }
    await sleep(1000);
  }
}

/* 라즈베리파이가 확정해 Jetson에 올린 인식 결과를 폴링한다. 시작 시점의 최신 scan_id 보다 새 것만 받는다
 * (파이·Jetson 시계를 비교하지 않으려고). 파이는 같은 객체를 한 번만 보내므로 이미 놓여 있던 상자는
 * 치웠다가 다시 놓아야 잡힌다. */
async function startScan() {
  const run = ++S.scanRun;
  show('scan');$('scanShoot').hidden=false;$('scanShoot').disabled=true; setScanState('', 'Jetson 연결 확인 중…');
  try {
    const res = await fetch('/api/unity/config', {cache:'no-store', signal:AbortSignal.timeout(2000)});
    const camera = res.ok ? await res.json() : null;
    if (S.scanRun !== run) return;
    $('scanShoot').disabled = !(camera && camera.enabled && camera.shoot);
    if (camera && camera.enabled) {
      setScanState('', 'Unity 가상 카메라 연결 중…');
      return streamUnityCamera(run);
    }
  } catch (_) { if (S.scanRun !== run) return; }
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

/* Unity 모드 「촬영」: 파이 PDA 서버(--cnn)가 그 순간 프레임 한 장을 분류해 min_conf 이상이면 Jetson에 올린다.
 * 화면은 웹캠 경로와 같이 Jetson의 새 scan_id로 설비를 확정한다(질의가 scan_id로 나가므로). */
async function shootScan() {
  const run = S.scanRun, btn = $('scanShoot');
  btn.disabled = true; setScanState('candidate', '분류 중…');
  try {
    const base = await latestScan();
    const r = await (await fetch('/api/unity/capture', {method:'POST', cache:'no-store', signal:AbortSignal.timeout(5000)})).json();
    if (S.scanRun !== run) return;
    const what = r.class + ' ' + Number(r.conf).toFixed(2);
    if (r.error) return setScanState('failed', r.error + ' — 다시 촬영');
    if (!r.confirmed) return setScanState('failed', '확신도 낮음(' + what + ') — 설비를 가까이 담아 다시 촬영');
    if (!r.sent) return setScanState('failed', what + ' — Jetson 전송 실패 · 다시 촬영');
    setScanState('candidate', what + ' — Jetson 확인 중…');
    for (let i = 0; i < 10; i++) {
      await sleep(SCAN_POLL_MS);
      if (S.scanRun !== run) return;
      const scan = await latestScan();
      if (!scan || (base && scan.scan_id === base.scan_id)) continue;
      const eq = scanTarget(scan, S.equipment);
      return eq ? lockScan(eq, scan) : setScanState('failed', (scan.code || scan.class) + ' — 현재 구성에 없는 설비 code · 검색 불가');
    }
    setScanState('failed', what + ' — Jetson 기록 확인 안 됨 · 다시 촬영');
  } catch (_) {
    if (S.scanRun === run) setScanState('failed', '촬영 실패 — 다시 촬영');
  } finally { btn.disabled = false; }
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
function equipmentGroups(equipment) {
  return equipment.reduce((groups, eq) => {
    const group = groups.find((g) => g.type === eq.type);
    if (group) group.equipment.push(eq); else groups.push({type:eq.type, equipment:[eq]});
    return groups;
  }, []);
}
function renderManualList() {
  const list = $('manualList'); list.innerHTML = '';
  equipmentGroups(S.equipment).forEach((group) => {
    const row = document.createElement('div'); row.className = 'eq-group';
    const title = document.createElement('h3'); title.textContent = group.type; row.appendChild(title);
    group.equipment.forEach((eq) => {
      const b = document.createElement('button'); b.type = 'button'; b.className = 'number-button';
      b.textContent = eq.code.slice(eq.type.length + 1); b.setAttribute('aria-label', eq.code + ' 선택');
      b.addEventListener('click', () => { setContext(eq, 'manual_selection', {}); haptic(30); show('ctx'); });
      row.appendChild(b);
    });
    list.appendChild(row);
  });
}
function layoutManualList() {
  const list=$('manualList');list.classList.remove('two-columns');
  const pane=list.parentElement;
  if (window.innerWidth>600 && pane.scrollHeight>pane.clientHeight && equipmentGroups(S.equipment).length>1 && equipmentGroups(S.equipment).every(g=>g.equipment.length<=8)) list.classList.add('two-columns');
}
function openManual() { renderRecent(); show('manual');requestAnimationFrame(layoutManualList); }

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
const fullStamp = (v) => {
  if (!v) return '시각 없음';
  const p = {}; new Intl.DateTimeFormat('en-US', { timeZone: 'Asia/Seoul', year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' })
    .formatToParts(new Date(v)).forEach((x) => { p[x.type] = x.value; });
  return p.year + '년 ' + p.month + '월 ' + p.day + '일 ' + p.hour + '시 ' + p.minute + '분 ' + p.second + '초';
};
const stamp = (v) => (v ? new Date(v).toLocaleTimeString('ko-KR', { timeZone: 'Asia/Seoul', hour12: false }) : '시각 없음');

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
  renderObsList(); renderMesStatus(); renderEquipmentMetrics();
  // 증상 순서는 관측에 따라 바뀐다. 순서가 달라졌을 때만 다시 그린다(목록 깜박임 방지).
  if (S.screen === 'ctx' && symKey(symptomsFor(eq)) !== S.symKey) renderSymptoms();
}

function clearMesObservations() {
  S.mes = null;
  S.observations = S.observations.filter((o) => o.source === 'manual');
  S.mesExcluded = [];
  renderObsList(); renderMesStatus(); renderEquipmentMetrics();
  if (S.screen === 'ctx') renderSymptoms();
}

function readingDetail(o, spec) {
  return '정상 범위 ' + fmt(spec.min) + '~' + fmt(spec.max) + ' ' + unitText(spec.unit)
    + (o.observed_at ? ' · 측정 ' + stamp(o.observed_at) : '');
}

/* 정상값 접기 상자. 펼침 상태는 목록별 key로 S.foldOpen에 남겨 3초 갱신으로 다시 그려도 닫히지 않는다.
 * noneShown — 늘 보이는 행(이탈·판정 불가·직접 입력)이 하나도 없을 때 「이상값 없음」을 앞에 붙인다. */
function normalFold(key, rows, hasStopped, noneShown) {
  const d = document.createElement('details');
  d.className = 'okfold';
  const s = document.createElement('summary');
  s.textContent = (noneShown ? '이상값 없음 · ' : '') + (hasStopped ? '정상·정지 중 ' : '정상 ') + rows.length + '개 보기';
  d.appendChild(s);
  rows.forEach((r) => d.appendChild(r));
  d.open = !!S.foldOpen[key];
  d.addEventListener('toggle', () => { S.foldOpen[key] = d.open; });
  return d;
}

/* 현재 센서와 답변의 고정 근거를 같은 표기로 표시한다. 질의 입력의 수동 덮어쓰기는 별도로 유지한다.
 * 표시만 나눈다 — 범위 이탈(▲▼)·범위 미설정·품질 미충족(excluded)은 늘 보이고, 정상·정지 중 0은 접는다. 판정(stateOf)은 그대로. */
function renderSensorReadings(box, readings, operating, foldKey, excluded) {
  const shown = [], folded = [];
  let hasStopped = false;
  readings.forEach((o) => {
    const spec = S.eq.signals.find((s) => s.signal === o.signal);
    if (!spec) return;
    const row = document.createElement('div');
    const stopped = spec.zeroStopped && o.value === 0 && operating && operating !== 'running';
    const status = stopped ? 'stopped' : stateOf(spec, o.value);
    const out = status === 'low' || status === 'high';
    row.className = 'obs' + (out ? ' out' : '');
    row.innerHTML = '<span class="txt"><span class="mono"></span><small></small></span>';
    row.querySelector('.mono').textContent = (status === 'low' ? '▼ ' : status === 'high' ? '▲ ' : '') + obsText(o);
    row.querySelector('small').textContent = readingDetail(o, spec) + ' · '
      + (stopped ? '정지 중 0' : status === 'low' ? '▼ 낮음' : status === 'high' ? '▲ 높음' : stateWord(status) || '범위 미설정');
    if (stopped) hasStopped = true;
    (stopped || status === 'normal' ? folded : shown).push(row);
  });
  // MES가 보냈지만 품질·단위·시각 규칙(usableReadings)에 걸려 판정에서 뺀 신호 — 값은 쓰지 않으므로 이름만.
  (excluded || []).forEach((sig) => {
    const row = document.createElement('div');
    row.className = 'obs';
    row.innerHTML = '<span class="txt"><span class="mono"></span><small></small></span>';
    row.querySelector('.mono').textContent = signalName(sig);
    row.querySelector('small').textContent = '품질·단위·측정 시각 미충족 · 판정 불가(조건 평가에서 제외)';
    shown.push(row);
  });
  shown.forEach((r) => box.appendChild(r));
  if (folded.length) box.appendChild(normalFold(foldKey || 'sensors', folded, hasStopped, !shown.length));
}

/* 범위 이탈이면 방향과 경계 대비 차이를 만든다. MES 운영 화면과 같은 표기. */
function obsView(o) {
  const spec = S.eq.signals.find((x) => x.signal === o.signal);
  // MES 운영 화면과 같이 정지 중 0 은 이탈로 강조하지 않는다. 카드 조건 판정(stateOf)은 어댑터 규칙 그대로.
  if (spec && spec.zeroStopped && o.value === 0 && S.mes && S.mes.operating !== 'running') return { st: 'stopped', text: '' };
  const st = stateOf(spec, o.value);
  if (st !== 'low' && st !== 'high') return { st: st, text: '' };
  const bound = st === 'low' ? spec.min : spec.max, diff = o.value - bound, u = unitText(o.unit);
  const bu = u === '%' ? '%' : u ? ' ' + u : '', du = u === '%' ? '%p' : bu;   // 비율의 차이는 %p
  return { st: st, text: (st === 'low' ? '▼ 하한 ' : '▲ 상한 ') + num(bound) + bu + ' 대비 '
    + (diff > 0 ? '+' : '') + num(diff) + du };
}

function renderObsList() {
  const box = $('obsList'); box.innerHTML = '';
  if (!S.eq) return;
  const rows = S.observations.map((o) => ({ o: o, v: obsView(o) }));
  const out = rows.filter((r) => r.v.text);
  const head = document.createElement('p');
  head.className = 'hint';
  head.textContent = 'MES 관측을 읽지 못했습니다. 직접 추가한 값만 사용합니다.';
  if (!S.mes) box.appendChild(head);
  const mk = (r) => {
    const row = document.createElement('div');
    row.className = 'obs' + (r.v.text ? ' out' : '');
    row.innerHTML = '<span class="txt"><span class="mono"></span><small></small></span>'
      + '<button class="x" type="button" aria-label="삭제">✕</button>';
    const spec = S.eq.signals.find((x) => x.signal === r.o.signal) || {};
    row.querySelector('.mono').textContent = signalName(r.o.signal) + ' = ' + r.o.value + (unitText(r.o.unit) ? ' ' + unitText(r.o.unit) : '');
    // 줄 나눔: 이탈·출처·정상 범위 / 측정 시각
    row.querySelector('small').textContent = (r.v.text ? r.v.text + ' · ' : r.v.st === 'stopped' ? '정지 중 0 · ' : '')
      + (r.o.source === 'manual' ? '직접 입력' : 'MES') + ' · 정상 범위 ' + fmt(spec.min) + '~' + fmt(spec.max) + ' ' + unitText(spec.unit)
      + (r.o.observed_at ? '\n측정 ' + fullStamp(r.o.observed_at) : '');
    row.querySelector('.x').addEventListener('click', () => {
      S.observations.splice(S.observations.indexOf(r.o), 1);
      if (r.o.source === 'mes') S.obsRemoved.push(r.o.signal);
      renderObsList();
    });
    return row;
  };
  // 범위 이탈을 먼저, 그다음 판정 불가(범위 미설정)·직접 입력값을 늘 보인다. MES 정상·정지 중 0만 접는다.
  // 직접 입력값은 작업자가 넣은 값이라 정상이어도 접지 않는다(넣은 값이 판정에 쓰이는지 바로 보이게).
  const fold = (r) => r.o.source !== 'manual' && (r.v.st === 'normal' || r.v.st === 'stopped');
  out.forEach((r) => box.appendChild(mk(r)));
  const shown = rows.filter((r) => !r.v.text && !fold(r));
  shown.forEach((r) => box.appendChild(mk(r)));
  const rest = rows.filter(fold);
  if (rest.length) box.appendChild(normalFold('obs', rest.map(mk), rest.some((r) => r.v.st === 'stopped'), !out.length && !shown.length));
}

const STATE_TXT = { running:'가동', stopped:'정지', waiting:'대기', normal:'정상', warning:'주의', critical:'자체 이상' };

function renderMesStatus() {
  const box = $('ctxMes');
  const sensors = $('ctxSensors'); sensors.innerHTML = '';
  if (S.mes) {
    renderSensorReadings(sensors, S.mes.readings || [], S.mes.operating, 'ctx', S.mesExcluded);
    if (!(S.mes.readings || []).length && !S.mesExcluded.length) sensors.textContent = '사용 가능한 센서값이 없습니다.';
  } else sensors.textContent = 'MES 연결을 확인해 주세요. 현재 센서값을 읽지 못했습니다.';
  const chat = $('chatMes');
  const out = S.observations.filter((o) => obsView(o).text).length;
  $('obsSummary').textContent = '관측값 · 직접 입력 — 범위 이탈 ' + out + '개';
  if (S.screen === 'ctx') renderAskSafety();
  if (!S.mes) {
    box.textContent = 'MES 상태를 읽지 못했습니다.'; box.classList.remove('bad');
    chatLine(chat, 'MES 상태를 읽지 못했습니다.', true);
    return;
  }
  const parts = ['MES ' + (STATE_TXT[S.mes.operating] || S.mes.operating || '—') + ' · '
    + (STATE_TXT[S.mes.fault] || S.mes.fault || '—')];
  if (S.mes.alarms.length) parts.push('경보 ' + S.mes.alarms.join(', '));
  parts.push('범위 이탈 ' + out + '개');
  S.mes.diagnoses.forEach((d) => parts.push('증상 후보: ' + d.symptom));
  box.textContent = parts.join(' · ');
  const bad = out > 0 || (!!S.mes.fault && S.mes.fault !== 'normal');
  if (bad && !S.sensorWasBad && !S.sensorsOpen) setSensorsOpen(true);
  S.sensorWasBad=bad;
  box.classList.toggle('bad', bad);
  chatLine(chat, parts.join(' · '), bad || S.mes.alarms.length > 0);
}

/* 대화 화면 상태 줄 — 설비 code·이름을 크게, MES 상태를 그 옆에. 대화 화면에서는 #ctx 띠를 숨기므로 설비 표시는 여기 하나다. */
function chatLine(el, status, bad) {
  el.innerHTML = '';
  if (S.eq) {
    const eq = document.createElement('b'); eq.className = 'eqc'; eq.textContent = S.eq.code + ' ' + (S.eq.group || '');
    el.appendChild(eq);
  }
  const st = document.createElement('span'); st.textContent = status;
  el.appendChild(st);
  el.classList.toggle('bad', bad);
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
      return { signal: r.o.signal, name: shortName(spec.name || r.o.signal), dir: r.st };
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
  note.hidden = items.length > 0;
  note.textContent = '이 설비에 등록된 추천 질문이 없습니다. 직접 적어 보내세요.';
  const pending = chatPending();
  items.forEach((item) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = item.score > 0 ? 'hot' : '';
    b.textContent = (item.score > 0 ? '▲ ' : '') + item.label;
    // MES 관련 이유를 칩 안에 보인다(A3 — 툴팁에만 두지 않는다). relevance()가 만든 값만, 중복 제거.
    if (item.score > 0 && item.why.length) {
      const w = document.createElement('span'); w.className = 'why-tag';
      w.textContent = ' · ' + Array.from(new Set(item.why)).join(' · ');
      b.appendChild(w);
    }
    b.title = item.text + (item.score > 0 ? ' · MES ' + item.why.join(' · ') : '');
    b.disabled = pending;
    b.addEventListener('click', () => { haptic(20); sendChat(item.text, item.label); });
    list.appendChild(b);
  });
  // 답이 나온 뒤에는 칩을 한 버튼으로 접는다 — 안전 카드·답·인계 버튼이 한 화면에 들어오게(A4). ▲는 MES 관련 칩 수.
  const compact = S.chat.length > 0 && items.length > 0;
  const foot = $('chatFoot'), tg = $('suggToggle');
  foot.classList.toggle('compact', compact);
  foot.classList.toggle('open', compact && !!S.suggOpen);
  tg.hidden = !compact;
  tg.textContent = '추천 질문 ' + items.length + '개' + (related.length ? ' · ▲' + related.length : '') + (S.suggOpen ? ' ▴' : ' ▾');
  tg.ariaExpanded = String(compact && !!S.suggOpen);
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
/* 안전 항목 한 줄 — 카드 title 원문 그대로(요약·잘라내기 없음)와 서버 공지의 멈춤 조건만 보인다(사용자 결정 10/13).
 * 카드 ID·safety_basis·know_how는 묶음 하나의 「안전수칙 자세히 ▾」(safetyMore)로 간다. 설비 불일치·카드 없음은
 * 접지 않고 경고 문구 그대로 항목에 보인다. opt.mark — 직전 답 대비 「추가」「변경」「빠짐」, opt.noStops — 직전 답과 같을 때. */
function safetyEl(c, opt) {
  opt = opt || {};
  const d = document.createElement('div');
  d.className = 'safety' + (c.mismatch || c.missing ? ' invalid' : '') + (opt.mark === '빠짐' ? ' gone' : '');
  const line = document.createElement('div'); line.className = 's-line';
  if (opt.mark) {
    const m = document.createElement('span'); m.className = 'mark'; m.textContent = opt.mark;
    line.appendChild(m);
  }
  const ttl = document.createElement('span'); ttl.className = 'ttl';
  if (c.mismatch) {
    ttl.textContent = '설비 불일치 — ' + c.eqCode + '에 해당하지 않는 안전 공지(' + c.card_id + ')';
  } else if (c.missing) {
    ttl.textContent = c.card_id + ' · 로컬 카드 없음 — 카드 원문을 확인할 수 없어 현재 설비와 대조하지 못했습니다';
  } else ttl.textContent = plain(c.title);
  line.appendChild(ttl);
  d.appendChild(line);
  if (c.mismatch) {
    const p = document.createElement('p'); p.className = 'basis';
    p.textContent = '지침 숨김 — 다른 설비의 안전 지침이므로 표시하지 않습니다. 담당자 확인';
    d.appendChild(p);
  }
  // 서버 공지의 멈춤 조건은 접지 않고 항목 바로 아래에 둔다(사용자 결정 원칙 2).
  if (!opt.noStops && opt.mark !== '빠짐') (c.mismatch ? [] : (c.stop_conditions || [])).forEach((t) => {
    const p = document.createElement('p');
    p.className = 'stop'; p.textContent = '멈춤 · ' + plain(t);
    d.appendChild(p);
  });
  return d;
}

/* 묶음 하나의 상세 — 카드별 ID·제목·근거 전문·know_how. 카드마다 상세 버튼을 두지 않는다(원칙 3). */
function safetyMore(cards) {
  const det = document.createElement('details'); det.className = 'safety-more';
  const sum = document.createElement('summary'); sum.textContent = '안전수칙 자세히';
  det.appendChild(sum);
  cards.forEach((c) => {
    const s = document.createElement('div'); s.className = 'sd' + (c.mismatch || c.missing ? ' invalid' : '');
    const add = (cls, text) => { const p = document.createElement('p'); p.className = cls; p.textContent = text; s.appendChild(p); };
    if (c.mismatch) {
      add('kid', c.card_id + ' · 설비 불일치');
      add('basis', '지침 숨김 — 다른 설비의 안전 지침이므로 표시하지 않습니다. 담당자 확인');
    } else {
      add('kid', c.missing ? c.card_id + ' · 로컬 카드 없음 · 설비 대조 불가' : c.card_id + ' · ' + c.tacit_type + ' · ' + c.grade);
      if (!c.missing) add('ttl', plain(c.title));
      add('basis', '근거 — ' + plain(c.safety_basis || '근거 미기재'));
      if (!c.missing && c.know_how) add('body', plain(c.know_how));
    }
    det.appendChild(s);
  });
  return det;
}

/* 안전 묶음 머리 — 관문 문구를 카드마다 반복하지 않고 여기 한 번 둔다. 설비 불일치 카드는 지킬 수칙 수에서 뺀다. */
function safetyHead(cards, lead) {
  const bad = cards.filter((c) => c.mismatch).length;
  return '⚠ ' + lead + ' ' + (cards.length - bad) + '건' + (bad ? ' · 설비 불일치 ' + bad + '건' : '')
    + ' — 안전 조건을 확인하고 준수한 뒤 작업하세요.';
}

/* 직전 답 대비 바뀐 점(원칙 5). 같음 = card_id 집합과 각 카드의 멈춤 조건이 모두 같다. */
const stopKey = (c) => (c.mismatch ? 'x' : '') + JSON.stringify(c.stop_conditions || []);
function safetyDiff(cards, prev) {
  const old = (id) => prev.find((p) => p.card_id === id);
  const mark = (c) => !old(c.card_id) ? '추가' : stopKey(old(c.card_id)) !== stopKey(c) ? '변경' : '';
  const gone = prev.filter((p) => !cards.some((c) => c.card_id === p.card_id));
  return {mark: mark, gone: gone, same: !gone.length && cards.every((c) => !mark(c))};
}

/* 머리 + 짧은 항목 + 「안전수칙 자세히 ▾」 하나. 답·대기 말풍선과 시도 화면이 같은 모양을 쓴다.
 * into(말풍선)를 주면 그 안에 바로 붙인다 — 머리가 말풍선 직계라야 sticky로 말풍선이 보이는 내내
 * pane 위에 고정된다(B1, A3 결정). prev — 직전 답의 안전 카드. 주면 같음 / 추가·변경·빠짐을 표시한다. */
function safetyGroup(cards, lead, into, prev) {
  const g = into || document.createElement('div');
  if (!into) g.className = 'safety-group';
  const diff = prev ? safetyDiff(cards, prev) : null;
  const list = document.createElement('div'); list.className = 'safety-cards' + (diff && diff.same ? ' compact' : '');
  const h = document.createElement('p'); h.className = 'safety-head';
  if (diff && diff.same) {
    const bad = cards.filter((c) => c.mismatch).length;
    h.textContent = '⚠ 안전사항 ' + (cards.length - bad) + '건' + (bad ? ' · 설비 불일치 ' + bad + '건' : '') + ' · 직전 답과 같음';
    cards.forEach((c) => list.appendChild(safetyEl(c, {noStops: true})));
  } else {
    const n = (m) => cards.filter((c) => diff.mark(c) === m).length;
    h.textContent = safetyHead(cards, lead) + (diff ? ' 직전 답 대비 추가 ' + n('추가') + ' · 변경 ' + n('변경')
      + ' · 빠짐 ' + diff.gone.length + '건.' : '');
    cards.forEach((c) => list.appendChild(safetyEl(c, {mark: diff ? diff.mark(c) : ''})));
    if (diff) diff.gone.forEach((c) => list.appendChild(safetyEl(c, {mark: '빠짐'})));
  }
  g.appendChild(h);
  g.appendChild(list);
  g.appendChild(safetyMore(cards));
  return g;
}

/* 시도 기록 화면의 안전 관문. 띠는 pane 직계로 붙어야 pane 전체 스크롤 동안 고정되므로 상자는
 * display:contents(pda.html .safety-stack). 항목은 짧게, 근거·상세는 묶음 하나로 접는다. */
function safetyStack(cards) {
  const box = document.createElement('div');
  box.className = 'safety-stack';
  const bar = document.createElement('div');
  bar.className = 'safety-bar';
  bar.textContent = safetyHead(cards, S.mes && S.mes.operating !== 'running' && safetyReason(true) !== '설비 이상' && safetyReason(true) !== '경보' && safetyReason(true) !== '증상 후보' ? '정지 중 — 작업 전 확인' : '작업 전 확인할 안전 수칙');
  box.appendChild(bar);
  const list = document.createElement('div'); list.className = 'safety-cards';
  cards.forEach((c) => list.appendChild(safetyEl(c)));
  box.appendChild(list);
  box.appendChild(safetyMore(cards));
  return box;
}


/* 대화 화면 위 상자 = 현재 설비의 안전 상태(원칙 4). 설비 code·MES 상태(safetyAlert)·이 설비 안전 수칙 건수.
 * 질의 전에는 카드 title 짧은 항목만, 질의가 시작되면 한 줄 상태로 줄인다. 전문(근거·know_how)은 싣지 않는다 —
 * 이 질의의 안전사항과 전문은 답 앞 묶음에 있다. 판정이 그대로면 다시 그리지 않는다. */
/* 안전 상자 머리의 이유 — 정지·이상·경보·증상 후보·범위 이탈을 구분한다. */
function safetyReason(hot) {
  const m = S.mes;
  if (!m) return 'MES 확인 불가';
  if (!hot) return 'MES 정상';
  if (m.fault && m.fault !== 'normal') return '설비 이상';
  if ((m.alarms || []).length) return '경보';
  if ((m.diagnoses || []).length) return '증상 후보';
  if (m.operating !== 'running') return 'MES 정지 중 · 설비 이상 없음';
  return '범위 이탈 또는 조건 일치';
}
/* 안전 수칙은 상단 바 한 곳에서 갱신한다. 사용자가 고른 펼침 상태는 갱신 중에도 유지한다. */
function renderAskSafety() {
  const box = $('askSafety');
  if (!S.eq) { box.innerHTML = ''; S.safetyView = null; return; }
  const base = rankCards(S.eq).safety;
  const cards = base.slice();
  S.chat.filter((t) => t.status === 'done' && t.ranked).forEach((t) => {
    t.ranked.safety.forEach((c) => {
      const i = cards.findIndex((x) => x.card_id === c.card_id);
      if (i >= 0) cards[i] = c;
      else cards.push(c);
    });
  });
  const hot = safetyAlert(S.mes, S.observations, cards);
  const reason = safetyReason(hot);
  const view = JSON.stringify([S.eq.equipment_id, cards, reason]);
  if (view === S.safetyView) return;
  S.safetyView = view;
  box.innerHTML = '';
  const g = document.createElement('details');
  g.open = !!S.safetyOpen;
  g.className = 'safety-group safety-fold' + (hot ? ' hot' : '');
  g.addEventListener('toggle', () => { S.safetyOpen = g.open; });
  const h = document.createElement('summary'); h.className = 'safety-head';
  h.textContent = S.eq.code + ' · 안전 수칙 ' + cards.filter((c) => !c.mismatch).length + '건 · ' + reason;
  g.appendChild(h);
  const content = document.createElement('div'); content.className = 'safety-content';
  cards.forEach((c) => content.appendChild(safetyEl(c)));
  if (cards.length) content.appendChild(safetyMore(cards));
  else {
    const empty = document.createElement('p');
    empty.textContent = '등록된 안전 수칙이 없습니다. 작업 전 현장 안전 절차를 확인하세요.';
    content.appendChild(empty);
  }
  g.appendChild(content);
  box.appendChild(g);
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

/* 답 말풍선에는 해결 답변을 표시하고, 안전 카드는 상단 바에서만 제공한다. */
function answerBody(turn) {
  const r = turn.ranked, res = turn.response;
  const d = document.createElement('div');
  const none = !res.review_queue && (res.no_knowledge === true || !res.answer);
  d.className = 'msg bot' + (none ? ' none' : '');
  const answer = document.createElement('p');
  answer.className = 'ans lead';
  answer.textContent = res.review_queue ? '답변을 보류했습니다. 담당자 검토가 필요합니다.'
    : none ? '해당 지식 없음 — 이 질문에 맞는 근거 카드가 없어 추측으로 답하지 않습니다. 증상을 더 구체적으로 적거나 숙련자에게 문의해 주세요.'
    : plain(res.answer);
  const row = document.createElement('div'); row.className = 'ans-row';
  row.appendChild(answer);
  d.appendChild(row);
  // 지식 카드를 찾지 못한 답 — 이 대화로 근무일지를 쓸지 묻는다. 고른 뒤에는 다시 묻지 않는다.
  if (none && !turn.reportAsked) {
    const ask = document.createElement('div'); ask.className = 'report-ask';
    ask.innerHTML = '<p>이 대화 내용으로 근무일지를 작성하시겠습니까?</p><button type="button" class="btn sm">아니오</button><button type="button" class="btn sm primary">네</button>';
    const [no, yes] = ask.querySelectorAll('button');
    no.addEventListener('click', () => { turn.reportAsked = 'no'; ask.remove(); });
    yes.addEventListener('click', () => { turn.reportAsked = 'yes'; ask.remove(); reportFromChat(turn); });
    d.appendChild(ask);
  }

  // 카드 답에서도 조치를 기록한다 — 본 카드 ID가 세션에 남아 대시보드 사건에 연결된다.
  const record = document.createElement('button');
  record.type = 'button'; record.className = 'btn sm';
  record.textContent = '조치 시작 — 기록하면서 작업';
  record.addEventListener('click', () => openResolve(turn));
  d.appendChild(record);
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
    renderSensorReadings(more, evidence, undefined, 'ev' + turn.id);
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

// ── 현장 조치 기록 ─────────────────────────────────────────────────
/* '해당 지식 없음' 뒤 조치하면서 남기는 기록. 조치 전·조치마다·마무리 때 MES 센서값은 서버가 자동으로 기록하고
 * (/api/resolution/*), 작업자는 본 것·부품·조치 칩·원인·결과만 고른다. 인계와 함께 저장되면 서버가
 * 검수 대기 카드 초안으로 만든다. 초안은 검색·PDA에 나가지 않고, 관리자 승인 뒤에 카드가 된다. */
const RESOLVE_RESULTS = [['resolved', '해결'], ['temporary', '임시조치'], ['failed', '효과 없음']];
// 서버 field_draft.SAFETY_WORDS와 같게 둔다. 화면 안내용이고, 잠금 응답 검사는 서버가 다시 한다.
const RISK_WORDS = ['재기동', '재가동', '재투입', '차단기', '개방', '커버', '충전', '바이패스', '분해', '전원 투입', '인터록', '잠금', '격리'];
const LOCKOUTS = ['예', '아니오', '해당 없음'];
const CAUSE_UNKNOWN = '원인 모름';

function riskyAction(text) { return RISK_WORDS.some((w) => String(text || '').includes(w)); }
// 카드 단계는 칩 글자가 잘려 있어도 서버가 단계 원문으로 판정한 risky를 따른다.
function liveRisky(live) { return riskyAction(live.action) || !!(live.card && live.card.risky); }

/* 조치 전(시작) 또는 조치 후(마무리) MES 요약 한 줄. */
function mesSummary(label, view) {
  if (!view) return label + ' MES 값을 기록하고 있습니다…';
  const out = view.out_of_range || [];
  const head = out.length ? out[0].name + ' ' + out[0].value + (out[0].state === 'low' ? ' ▼' : ' ▲')
    + (out.length > 1 ? ' 외 ' + (out.length - 1) : '') : '이상 신호 없음';
  return label + ' MES 자동 기록 · ' + stamp(view.simulated_at) + ' · ' + head
    + ' · ' + ((view.alarms || []).length ? '경보 ' + view.alarms.join(', ') : '경보 없음');
}

/* 저장 전 검사. 서버도 같은 규칙으로 다시 검사한다. */
function resolveError(r) {
  if (!r.sessionId) return '조치 기록을 시작하지 못했습니다. 이전으로 돌아가 다시 시도해 주세요.';
  if (!r.symptom.trim()) return '현장에서 본 것을 한 줄 적어 주세요.';
  if (!r.componentId) return '부품을 골라 주세요.';
  if (r.result !== 'failed' && !r.steps.length) return '조치를 하나 이상 완료해 주세요.';
  if (!(r.cause || r.causeCustom.trim())) return '원인을 골라 주세요. 모르면 "원인 모름"을 누릅니다.';
  if (!r.result) return '결과를 골라 주세요.';
  return '';
}

/* 인계 본문의 resolution. 조치·센서 기록은 서버가 세션에서 채운다. */
function sessionPayload(r) {
  return {session_id: r.sessionId, symptom: r.symptom.trim(), cause: (r.causeCustom.trim() || r.cause),
    component_id: r.componentId, result: r.result};
}

/* 인계 응답의 draft 필드 → 확인 문구. 응답에는 카드 내용이 없다.
 * mes_verdict(조치 기록): recovered·not_yet·unconfirmed. 없으면 예전 mes_recovered로 판단한다. */
const MES_VERDICT_TEXT = {recovered: 'MES 정상 복귀 확인', not_yet: 'MES는 아직 이상 — 해결로 세지 않습니다',
  unconfirmed: 'MES 확인 불가(복구 기록 없음) — 해결로 세지 않습니다'};
function draftNotice(draft) {
  if (!draft) return '';
  const mes = MES_VERDICT_TEXT[draft.mes_verdict]
    || (draft.mes_recovered === true ? MES_VERDICT_TEXT.recovered : draft.mes_recovered === false ? MES_VERDICT_TEXT.not_yet : '');
  return draftReason(draft.reason) + (mes ? ' · ' + mes : '');
}

function draftReason(reason) {
  if (reason === 'pending_review') return '이 조치 기록으로 카드 초안이 만들어졌고 관리자 검수를 기다립니다 — 승인 전에는 검색에 나오지 않습니다';
  if (reason === 'attempt_only') return '효과 없음으로 시도 기록만 남겼습니다. 카드 초안은 만들지 않습니다.';
  if (reason === 'supporting') return '같은 원인의 검수 대기 카드 초안에 이 기록을 근거로 더했습니다';
  if (reason === 'contradicting') return '같은 조치가 효과 없었던 기록으로 검수 대기 카드 초안에 남겼습니다.';
  if (reason === 'card_used') return '카드를 보고 한 조치로 기록했습니다. 새 카드 초안은 만들지 않습니다.';
  if (reason === 'invalid') return '조치 기록을 담았지만 카드 형식이 맞지 않아 담당자 보완 대기로 보관했습니다.';
  return '이 인계에는 이미 카드 초안이 만들어져 있어 새로 만들지 않았습니다.';
}

async function postJson(path, body) {
  const res = await api(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
  return data;
}

function resolveWarn(text) { $('resWarn').hidden = !text; $('resWarn').textContent = text || ''; }

async function openResolve(turn) {
  S.res = {turn: turn, sessionId: null, before: null, components: [], actions: [], causes: [CAUSE_UNKNOWN],
    steps: [], live: null, phase: 'work', verdict: null, symptom: '', componentId: '', cause: '', causeCustom: '',
    result: null, busy: true};
  $('resSymptom').value = ''; $('resCustom').value = ''; $('resCauseCustom').value = '';
  resolveWarn('');
  renderResolve();
  show('resolve');
  try {
    const out = await postJson('/api/resolution/start', {equipment_id: S.eq.equipment_id, question: turn.question,
      evidence: (turn.response && turn.response.evidence) || null,
      card_ids: ((turn.ranked && turn.ranked.actions) || []).map((x) => x.card.card_id)});
    Object.assign(S.res, {sessionId: out.session_id, before: out.before, components: out.components || [],
      actions: out.action_suggestions || [], causes: out.cause_suggestions || [CAUSE_UNKNOWN]});
    const pick = S.res.components.find((c) => c.suggested);
    if (pick) S.res.componentId = pick.component_id;
  } catch (err) {
    resolveWarn('조치 기록을 시작하지 못했습니다 · ' + err.message);
  } finally { S.res.busy = false; renderResolve(); }
}

function chip(text, pressed, onClick, extra, disabled) {
  const b = document.createElement('button');
  b.type = 'button'; b.className = 'chip'; b.textContent = text; b.disabled = !!disabled;
  if (pressed !== null) b.setAttribute('aria-pressed', String(pressed));
  if (extra) { const s = document.createElement('small'); s.textContent = extra; b.appendChild(s); }
  b.addEventListener('click', () => { haptic(15); onClick(); });
  return b;
}

function renderResolve() {
  const r = S.res;
  if (!r) return;
  $('resBefore').textContent = r.phase === 'wrap' && r.verdict ? mesSummary('조치 후', r.verdict.after) : mesSummary('조치 전', r.before);
  $('resWork').hidden = r.phase !== 'work';
  $('resWrap').hidden = r.phase !== 'wrap';
  $('resSave').hidden = r.phase !== 'wrap';
  // 부품
  $('resComponents').replaceChildren(...r.components.map((c) => chip(c.name, r.componentId === c.component_id,
    () => { r.componentId = c.component_id; renderResolve(); }, c.suggested ? 'MES 추천' : '')));
  // 끝낸 조치
  $('resSteps').replaceChildren(...r.steps.map((s) => {
    const li = document.createElement('li'); li.className = 'res-step';
    const a = document.createElement('b'); a.textContent = s.order + '. ' + s.action;
    const res = document.createElement('span'); res.className = 'res';
    res.textContent = (s.card ? s.card.card_id + ' 단계 · ' : '') + (s.mes_linked ? 'MES 반영 · ' : '') + '자동 결과: ' + s.result_text;
    li.append(a, res);
    if (s.lockout) { const l = document.createElement('span'); l.className = 'lock'; l.textContent = '에너지 차단(잠금): ' + s.lockout; li.appendChild(l); }
    return li;
  }));
  // 진행 중인 조치
  const live = $('resLive');
  live.hidden = !r.live;
  $('resPick').hidden = !!r.live;
  if (r.live) {
    const title = document.createElement('b'); title.textContent = (r.steps.length + 1) + '. ' + r.live.action + ' · 진행 중';
    const parts = [title];
    const needLock = liveRisky(r.live);
    if (needLock) {
      const box = document.createElement('div'); box.className = 'res-lock';
      box.textContent = '차단기·재투입·재가동 같은 작업입니다. 에너지 차단(잠금) 후 작업했나요?';
      const row = document.createElement('div'); row.className = 'chips';
      row.append(...LOCKOUTS.map((v) => chip(v, r.live.lockout === v, () => { r.live.lockout = v; renderResolve(); })));
      box.appendChild(row); parts.push(box);
    }
    const done = document.createElement('button');
    done.type = 'button'; done.className = 'btn primary'; done.textContent = '완료 — 지금 센서값 기록';
    done.disabled = r.busy || (needLock && !r.live.lockout);
    done.addEventListener('click', completeStep);
    const cancel = document.createElement('button');
    cancel.type = 'button'; cancel.className = 'btn sm ghost'; cancel.textContent = '이 조치 취소';
    cancel.addEventListener('click', () => { r.live = null; renderResolve(); });
    parts.push(done, cancel);
    live.replaceChildren(...parts);
  }
  $('resActionChips').replaceChildren(...actionChips(r).map((a) => {
    const c = chip(a.text, null, () => { r.live = {action: a.text, lockout: null, card: a.card}; renderResolve(); }, a.tag, a.disabled);
    if (a.card) c.classList.add('card-step');
    return c;
  }));
  $('resFinish').disabled = r.busy || !r.sessionId || !!r.live || !r.steps.length;
  $('resFinish').textContent = r.steps.length ? '조치 마무리 — 조치 후 MES 확인' : '조치 마무리 (조치를 하나 이상 완료하면 켜짐)';
  // 마무리
  if (r.phase === 'wrap' && r.verdict) {
    const v = $('resVerdict');
    v.className = 'res-verdict ' + (r.verdict.verdict === 'recovered' ? 'good' : 'bad');
    v.textContent = '조치 후 자동 확인 · ' + r.verdict.text;
    $('resResult').replaceChildren(...RESOLVE_RESULTS.map(([k, t]) => chip(t, r.result === k,
      () => { r.result = k; renderResolve(); }, r.verdict.suggested_result === k ? 'MES 제안' : '')));
    $('resCauses').replaceChildren(...r.causes.map((c) => chip(c, r.cause === c && !r.causeCustom.trim(),
      () => { r.cause = c; r.causeCustom = ''; $('resCauseCustom').value = ''; renderResolve(); })));
  }
  $('resSave').disabled = r.busy;
}

/* 한 일 칩: 답에서 본 카드의 단계(완료하면 '카드 방법'으로 남음), MES 복구 단계(완료하면 MES에도 반영, 순서대로),
 * 재가동(MES 단계를 다 끝낸 뒤), 이 설비의 이전 현장 기록. 이미 끝낸 카드·MES 단계는 다시 보이지 않는다. */
const ACTION_TAGS = {mes_recovery: 'MES 단계', mes_restart: 'MES', field_record: '이전 기록'};
function actionChips(r) {
  const done = new Set(r.steps.map((s) => s.action));
  const mesSteps = r.actions.filter((a) => a.source === 'mes_recovery');
  const mesDone = mesSteps.every((a) => done.has(a.text));
  return r.actions.filter((a) => !(a.source !== 'field_record' && done.has(a.text)))
    .map((a) => ({text: a.text, disabled: a.source === 'mes_restart' && !mesDone,
      tag: a.source === 'card_step' ? a.card_id + (a.n ? ' · ' + a.n + '단계' : '') : ACTION_TAGS[a.source] || '',
      card: a.source === 'card_step' ? {card_id: a.card_id, step_id: a.step_id, risky: !!a.risky} : null}));
}

async function completeStep() {
  const r = S.res;
  if (!r || !r.live || r.busy) return;
  r.busy = true; renderResolve();
  try {
    const card = r.live.card;
    const out = await postJson('/api/resolution/' + r.sessionId + '/step', {action: r.live.action, lockout: r.live.lockout,
      ...(card ? {card_id: card.card_id, step_id: card.step_id} : {})});
    r.steps.push({order: out.order, action: r.live.action, lockout: liveRisky(r.live) ? r.live.lockout : null,
      result_text: out.result_text, mes_linked: out.mes_linked || null, card: card || null});
    r.live = null; resolveWarn('');
  } catch (err) {
    resolveWarn(err.message === 'lockout_required' ? '잠금 여부를 골라 주세요.' : '조치를 기록하지 못했습니다 · ' + err.message);
  } finally { r.busy = false; renderResolve(); }
}

async function finishResolve() {
  const r = S.res;
  if (!r || r.busy) return;
  r.busy = true; renderResolve();
  try {
    r.verdict = await postJson('/api/resolution/' + r.sessionId + '/finish', {});
    r.result = r.verdict.suggested_result; r.phase = 'wrap'; resolveWarn('');
  } catch (err) {
    resolveWarn('조치 후 MES를 확인하지 못했습니다 · ' + err.message);
  } finally { r.busy = false; renderResolve(); }
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

// 아는 것만 말한다 — 경과 초와 이 화면의 시간 제한(QUERY_TIMEOUT_MS). 서버가 단계 정보를 주지 않으므로 단계는 지어내지 않는다.
const waitText = (t) => '답변 작성 중 · ' + Math.floor((Date.now() - t.started) / 1000) + '초 경과 · 최대 '
  + Math.round(QUERY_TIMEOUT_MS / 1000) + '초';

function botBubble(t) {
  if (t.status === 'done') return answerBody(t);
  const d = document.createElement('div');
  const p = document.createElement('p'); p.className = 'ans';
  if (t.status === 'pending') {
    d.className = 'msg bot wait'; d.id = 'turn-' + t.id;
    const row = document.createElement('div'); row.className = 'wait-row';
    p.textContent = waitText(t);
    row.appendChild(p);
    d.appendChild(row);
  } else {
    d.appendChild(p);
    d.className = 'msg bot err';
    p.textContent = t.status === 'cancelled' ? '취소했습니다. 이 질문의 답은 표시하지 않습니다.'
      : '질의 실패 · ' + t.error + ' — 같은 질문을 다시 보내 주세요.';
  }
  return d;
}

function renderChat() {
  const log = $('chatLog'); log.innerHTML = '';
  $('chatPane').classList.toggle('centered-state', S.chat.length <= 1);
  $('chatCancelDock').hidden = !chatPending();
  let last = null;
  S.chat.forEach((t) => { log.appendChild(userBubble(t)); last = botBubble(t); log.appendChild(last); });
  renderAskSafety();
  if (last) scrollToTurn(last);
}

/* 새 답변을 대화 스크롤 안에 표시한다. 안전 바는 이 스크롤 밖에 있다. */
function scrollToTurn(el) {
  const pane = $('chatPane');
  if (!pane || !el.getBoundingClientRect) return;
  const base = pane.getBoundingClientRect().top - pane.scrollTop;
  let y = el.getBoundingClientRect().top - base - 8;
  const tail = el.querySelector('.ans-next') || el.querySelector('.wait-row') || el.querySelector('.ans');
  if (tail) {
    const bottom = tail.getBoundingClientRect().bottom - base + 8;
    if (bottom - y > pane.clientHeight) y = bottom - pane.clientHeight;
  }
  pane.scrollTop = Math.max(0, y);
}

async function sendChat(question, label) {
  question = String(question || '').trim();
  if (!question || !S.eq || !S.source || chatPending()) return;
  const turn = {id: ++S.chatSeq, question: question, label: label && label !== question ? label : '',
    status: 'pending', started: Date.now(), eqId: S.eq.equipment_id};
  S.chat.push(turn);
  if (!label) $('question').value = '';
  S.tries = []; S.attemptSeq = 0; S.suggOpen = false;
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
  if (S.screen === 'ctx') { renderChat(); renderSymptoms(); }
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
const HO_DONE = ['closed', 'done', 'withdrawn'];

/* 「이 기기에서 확인함」 작업 체크 — 이 PDA의 localStorage에만 둔다. 서버로 보내지 않고 인계 상태(open·needs_recheck…)도
 * 바꾸지 않는다(MES 수치가 돌아와도 자동 완료하지 않는 원칙과 같은 선). 키: shiftlink.hoCheck.<handover_id>.<item_id>,
 * item_id가 없으면 i<인덱스>-<문구 해시>. 값: 체크한 시각(ISO). 저장소가 막혀도 이 탭 동안은 메모리 사본으로 동작한다. */
const HO_CHECK_PREFIX = 'shiftlink.hoCheck.';
const hoChecks = {};
function textHash(t) {
  let h = 5381;
  for (const ch of String(t)) h = ((h * 33) ^ ch.codePointAt(0)) >>> 0;
  return h.toString(36);
}
function hoItemKey(h, it, i) {
  return HO_CHECK_PREFIX + h.handover_id + '.' + (it.item_id || it.id || ('i' + i + '-' + textHash(it.text)));
}
function hoCheckedAt(key) {
  if (key in hoChecks) return hoChecks[key];
  try { return localStorage.getItem(key) || ''; } catch (_) { return ''; }
}
function setHoChecked(key, on) {
  hoChecks[key] = on ? new Date().toISOString() : '';
  try { if (on) localStorage.setItem(key, hoChecks[key]); else localStorage.removeItem(key); } catch (_) { /* 메모리 사본만 */ }
}
const hhmm = (iso) => new Date(iso).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });

/* 확인 체크 칸 — 네이티브 체크박스 + label(행 높이 전체가 클릭 영역, Space 동작). onChange는 저장 뒤 호출. */
function hoCheckEl(key, onChange) {
  const label = document.createElement('label');
  label.className = 'ho-check';
  const box = document.createElement('input');
  box.type = 'checkbox'; box.dataset.key = key;
  const word = document.createElement('span');
  const paint = () => {
    const at = hoCheckedAt(key);
    box.checked = !!at;
    word.textContent = at ? '확인함 ' + hhmm(at) : '확인';
    label.classList.toggle('on', !!at);
  };
  paint();
  box.addEventListener('change', () => { setHoChecked(key, box.checked); paint(); if (onChange) onChange(); });
  label.appendChild(box); label.appendChild(word);
  return label;
}

/* 문구에 적힌 설비 code(현재 구성에 있는 것만). 지어내지 않는다 — 없으면 빈 배열. */
const hoCodes = (text) => S.equipment.filter((e) => String(text).includes(e.code)).map((e) => e.code);

/* 홈 인계 목록 — 미완료 항목 전부, 확인한 항목은 아래로(숨기지 않음). 같은 묶음 안 순서는 인계 기록 순서. */
function renderHomeHandovers() { renderHome(); }

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

/* code — 홈 목록에서 올 때 그 항목의 설비 code('' = 전체). 버튼 배선(ev만 넘어옴)은 지금처럼 선택 설비 기준. */
function handoverEquipment(h, equipment) {
  const ids = new Set([h.equipment_id, ...(h.equipment_ids || [])].filter(Boolean));
  const text = [h.memo_text, ...((h.open_items || []).map((it) => it.text))].join(' ');
  return equipment.filter((eq) => ids.has(eq.equipment_id) || text.split(/[^A-Za-z0-9-]+/).includes(eq.code));
}
function dutyTimeline(h, eq) {
  if (h.kind === 'work_log') return [{time:h.required_context.start_at || h.created_at, author:h.required_context.author || '미기재', action:h.memo_text}];
  return (h.open_items || []).filter((it) => !eq || String(it.text).split(/[^A-Za-z0-9-]+/).includes(eq.code))
    .map((it) => ({time:h.created_at || h.shift_date, author:h.author_name || h.author_persona_id || '미기재', action:it.text, status:it.status, basis:it.basis_ids || []}));
}
function allHandovers() {
  const ids = new Set(S.savedHandovers.map((h) => h.handover_id));
  return [...S.savedHandovers, ...S.handovers.filter((h) => !ids.has(h.handover_id))];
}
async function refreshSavedHandovers() {
  try { S.savedHandovers = (await getJson('/api/outbox/pending')).handovers || []; renderHome(); }
  catch (_) { /* 보존된 정적 인계는 연결 끊김에도 열 수 있다. */ }
}
function handoverCard(h) {
  const card = document.createElement('button'); card.className = 'summary-card'; card.type = 'button';
  const info = document.createElement('div');
  const title = document.createElement('div'); title.className = 'title'; title.textContent = h.kind === 'work_log' ? '근무일지' : '당직일지';
  const meta = document.createElement('p'); meta.className = 'hint';
  meta.textContent = (h.shift_date || (h.created_at || '').slice(0,10)) + ' · ' + (h.author_name || h.author_persona_id || (h.required_context || {}).author || '담당자 미기재');
  const equipments = document.createElement('p');
  const targets = handoverEquipment(h, S.equipment); equipments.textContent = targets.map((eq) => eq.code).join(' · ') || '대상 장비 미기재';
  const badge = document.createElement('span'); badge.className = 'pill miss';
  const open = (h.open_items || []).filter((it) => !['closed','done','withdrawn'].includes(it.status));
  badge.textContent = open.length ? '조치 필요 ' + open.length + '건' : '일지 보기';
  info.append(title,meta,equipments); card.append(info,badge);
  card.addEventListener('click', () => openDutyDetail(h, S.screen)); return card;
}
function renderHome() {
  const home = $('homeHandover'); if (!home) return; home.replaceChildren();
  const rows = allHandovers(); appendTimeline(home, rows.flatMap(h=>dutyTimeline(h)));
  const operator=S.operator||{};
  $('homeGreeting').textContent='안녕하세요, '+(operator.name||operator.id||'작업자')+'님';
  $('homeWorkDate').textContent=new Date().toLocaleString('ko-KR',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'})+' · '+shiftAt().code+'조 '+SHIFT_HOURS[shiftAt().code];
  const recent=rows.slice().sort((a,b)=>String(b.created_at||b.shift_date||'').localeCompare(String(a.created_at||a.shift_date||'')))[0];
  const previous=recent&&(recent.author_name||(recent.required_context||{}).author||recent.author_persona_id);
  $('homeShiftPeople').textContent='이전 근무자 '+(previous||'미등록')+' · 다음 근무자 '+(operator.next_worker_name||'미등록');
  $('homeHandoverCount').textContent=rows.length+'건';
  const faultDetails=$('homeFaultDetails');faultDetails.replaceChildren();
  if(!S.snapshot||S.online===false)faultDetails.textContent='연결 상태를 확인해 주세요.';
  else if(!(S.faults||[]).length)faultDetails.textContent='현재 감지된 이상이 없습니다.';
  else (S.faults||[]).forEach((fault)=>{const p=document.createElement('p');p.textContent=fault.eq.code+' · '+fault.items.join(' · ');if(S.faults.length>1)p.prepend(eqChip(fault.eq.equipment_id));faultDetails.appendChild(p);});
  if (!rows.length) home.textContent = '등록된 인계 사항이 없습니다.';
  const counts = [['전체 설비', S.equipment.length], ['가동 중', (S.snapshot && S.snapshot.equipment || []).filter((e) => e.operating_state === 'running').length], ['확인 필요', (S.faults || []).length]];
  const metrics = $('homeDashboard'); metrics.replaceChildren();
  counts.forEach(([label,value]) => metrics.appendChild(metricElement(label, S.snapshot && S.online !== false ? value : (label === '전체 설비' ? value : '—'))));
  // 이상이 없으면 회색 상자는 숨긴다(조치 필요 장비 0이 같은 말) — 그 자리에 지켜볼 설비. 이상이 있으면 지켜볼 설비를 숨긴다
  faultDetails.hidden = !!S.snapshot && S.online !== false && !(S.faults || []).length;
  $('homeWatch').classList.toggle('busy', !!(S.faults || []).length);
  renderHomeMade();
}
function metricElement(label, value, unit, bad) {
  const el = document.createElement('div'); el.className = 'metric' + (bad ? ' bad' : '');
  const title = document.createElement('span'); title.className = 'label'; title.textContent = label;
  const number = document.createElement('span'); number.className = 'value'; number.textContent = String(value);
  if (unit) { const u = document.createElement('span'); u.className = 'unit'; u.textContent = unit; number.appendChild(u); }
  el.append(title,number); return el;
}
function setSensorsOpen(open) {
  S.sensorsOpen = open;
  S.sensorSnapshot = null;
  $('equipmentWorkspace').classList.toggle('sensors-open', open);
  $('toggleChat').textContent = open ? '센서값 닫기' : '센서값 열기';
  $('toggleChat').setAttribute('aria-expanded', String(open));
  renderEquipmentMetrics();
}
function renderEquipmentMetrics() {
  const box = $('equipmentMetrics'); if (!box || !S.eq) return; box.replaceChildren();
  if (S.sensorsOpen && !S.sensorSnapshot && S.mes) S.sensorSnapshot = JSON.parse(JSON.stringify(S.mes));
  const mes = S.sensorsOpen ? S.sensorSnapshot : S.mes;
  const measurements = mes ? (mes.readings || []) : [];
  S.eq.signals.forEach((spec) => {
    const row = measurements.find((m) => m.signal === spec.signal);
    const state = row && stateOf(spec, row.value);
    const idle = row && spec.zeroStopped && row.value === 0 && mes.operating !== 'running';
    const el = idle ? metricElement(shortName(spec.name), '정지 중') : metricElement(shortName(spec.name), row ? num(row.value) : '—', unitText(spec.unit), state === 'low' || state === 'high');
    if (idle) el.classList.add('idle');
    box.appendChild(el);
  });
  $('metricsTime').textContent = mes ? '측정 시각 · ' + fullStamp(mes.at) + (S.sensorsOpen ? ' · 고정된 값' : '')
    + (!S.mes ? ' · 현재 MES 연결 끊김' : '') : 'MES 데이터를 수신하지 못했습니다.';
}
function openHandover() {
  const pane = $('hoPane'); pane.replaceChildren();
  appendTimeline(pane,allHandovers().flatMap(h=>dutyTimeline(h)));
  if (!pane.children.length) pane.textContent = '등록된 인계 기록이 없습니다.';
  show('handover');
}
function appendTimeline(pane, rows) {
  if (!rows.length) { const p = document.createElement('p'); p.className = 'hint'; p.textContent = '등록된 조치 기록이 없습니다.'; pane.appendChild(p); return; }
  const table = document.createElement('table'); table.className = 'timeline';
  table.innerHTML = '<thead><tr><th>당직자 이름</th><th>시간</th><th>조치사항</th></tr></thead>';
  const body = document.createElement('tbody');
  rows.forEach((row) => {
    const tr = document.createElement('tr');
    [row.author, row.time ? (Number.isFinite(Date.parse(row.time)) ? new Date(row.time).toLocaleString('ko-KR',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}) : row.time) : '미기재', row.action].forEach((text) => { const td = document.createElement('td'); td.textContent = text; tr.appendChild(td); });
    if (row.status) { const tag = document.createElement('span'); tag.className = 'pill status-' + row.status; tag.textContent = handoverStatus(row.status)[0]; tr.lastChild.prepend(tag,document.createElement('br')); }
    if (row.basis) appendBasisDetails(tr.lastChild, row.basis);
    body.appendChild(tr);
  }); table.appendChild(body); pane.appendChild(table);
}
function openDutyDetail(h, back) {
  const pane = $('dutyPane'); pane.replaceChildren();
  const meta = document.createElement('p'); meta.className = 'lbl';
  meta.textContent = h.handover_id + ' · ' + (h.created_at || h.shift_date || '') + ' · 이전 담당자 ' + (h.author_name || h.author_persona_id || (h.required_context || {}).author || '미기재');
  const target = document.createElement('p'); target.textContent = handoverEquipment(h,S.equipment).map((eq) => eq.code).join(' · ');
  const memo = document.createElement('p'); memo.className = 'body'; memo.textContent = h.memo_text;
  pane.append(meta,target,memo); appendTimeline(pane, dutyTimeline(h));
  $('dutyBack').onclick = goBack;
  // 읽음 확인은 조치 상태나 정렬을 바꾸지 않는다. 이 단말에만 저장한다.
  const ack = document.createElement('button'); ack.type = 'button'; ack.className = 'btn ghost'; ack.textContent = '읽음 확인'; ack.hidden = true;
  const key = 'shiftlink.handover.read.' + h.handover_id;
  try { if (localStorage.getItem(key)) ack.textContent = '읽음 확인 완료'; } catch (_) {}
  ack.onclick = () => { try { localStorage.setItem(key,new Date().toISOString()); ack.textContent = '읽음 확인 완료'; } catch (_) { ack.textContent = '단말 저장 실패 · 다시 확인'; } };
  const end = document.createElement('div'); end.setAttribute('aria-hidden','true'); end.style.minHeight = '1px'; pane.append(end,ack);
  const checkEnd = () => { if (pane.scrollHeight - pane.scrollTop - pane.clientHeight < 80) ack.hidden = false; };
  pane.onscroll = checkEnd; show('dutyDetail'); requestAnimationFrame(checkEnd);
}
function openHistory() {
  if (!S.eq) return;
  const pane = $('historyPane'); pane.replaceChildren(); $('historyTitle').textContent = S.eq.code + ' · '+S.eq.group+' · 정비이력';
  const rows = allHandovers().flatMap((h) => {
    if (h.kind === 'work_log') return handoverEquipment(h,S.equipment).includes(S.eq) ? dutyTimeline(h,S.eq) : [];
    return dutyTimeline(h,S.eq);
  }); appendTimeline(pane,rows); show('history');
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
  try { const pending=JSON.parse(localStorage.getItem(HANDOVER_PENDING_KEY)||'null'); if(pending&&pending.kind==='work_log'){openReport();return;} } catch (_) {}
  S.hoNewBack = S.screen === 'ctx' ? 'chat' : 'ctx';
  S.resolution = null;
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

/* 근무일지용: 관측 시각은 맨 위에 한 번, 측정값 앞에 정상/비정상 */
function reportMesContext(snap, events, eqs) {
  const blocks = eqs.map((eq) => {
    const recent = (events || []).filter((e) => e.equipment_id === eq.equipment_id).slice(-5);
    return [eq.code, ...usableReadings(snap, eq).kept.map((m) => {
      const spec = eq.signals.find((s) => s.signal === m.signal), st = stateOf(spec, m.value);
      return (st === 'normal' ? '정상' : st ? '비정상' : '기준 없음') + ' · ' + (spec.name || m.signal) + ': ' + m.value + ' ' + unitText(m.unit);
    }), ...recent.map((e) => '이벤트 · ' + e.occurred_at + ' · ' + e.observation)].join('\n');
  });
  return ['관측 시각 · ' + snap.simulated_at, ...blocks].join('\n\n');
}

/* 다시 불러와도 이미 입력에 있는 줄(측정값·이벤트)은 붙이지 않는다. 새 줄이 없으면 null. */
function appendMesContext(current, text) {
  const have = new Set(current.split('\n').map((line) => line.trim()));
  const [head, ...lines] = text.split('\n');
  const fresh = lines.filter((line) => !have.has(line.trim()));
  if (!fresh.length) return null;
  return [current.trim(), [head, ...fresh].join('\n')].filter(Boolean).join('\n\n');
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
    const combined = appendMesContext(input.value, text);
    if (combined === null) { $('hoMesStatus').textContent = '새로 추가할 MES 기록이 없습니다. 이미 넣은 측정값·이벤트는 다시 붙이지 않습니다.'; return; }
    if (combined.length > input.maxLength) throw new Error('입력 가능한 글자 수를 초과합니다. 기존 내용을 줄인 뒤 다시 불러와 주세요.');
    input.value = combined;
    $('hoMesStatus').textContent = 'MES 기록을 추가했습니다. 필요한 내용을 수정해 주세요.';
    validateHandover();
  } catch (err) { $('hoMesStatus').textContent = '센서값을 불러오지 못했습니다. ' + err.message; }
  finally { button.disabled = false; }
}

function validateHandover() {
  const ok = ['hoMemo', 'hoCtx', 'hoRole', 'hoTiming', 'hoChannel', 'hoAck'].every((id) => $(id).value.trim());
  $('hoSave').disabled = !ok;
  $('hoWarn').hidden = ok;
}


/* 대시보드 요약(작업자용). 이미 3초마다 읽는 /api/state와 인계 기록만 쓴다. faults는 faultsFrom() 결과. */
const LINE_MODE_TXT = { running:'운전 중', paused:'일시정지', stopped:'정지', fault:'고장 발생', recovering:'복구 관찰', quality_hold:'제품 검사·보류' };
// ponytail: 후속 대기는 wait_reason으로 가린다 — 소재 부족·계획 정지·복구 관찰은 고장 때문이 아니다. 새 사유가 생기면 이 목록에.
const PLAIN_WAIT = ['material_shortage', 'planned_stop', 'recovery'];
function dashSummary(snap, equipment, handovers, faults) {
  const code = (id) => (equipment.find((e) => e.equipment_id === id) || {}).code || id;
  const waiting = (snap.equipment || []).filter((e) => e.operating_state === 'waiting' && e.wait_reason && !PLAIN_WAIT.includes(e.wait_reason));
  const openItems = (handovers || []).flatMap((h) => h.open_items || []).filter((it) => !['closed', 'done', 'withdrawn'].includes(it.status));
  return {
    mode: snap.line_mode,
    line: (snap.simulated_at ? new Date(snap.simulated_at).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }) + ' ' : '') + '라인 ' + (LINE_MODE_TXT[snap.line_mode] || snap.line_mode || '상태 확인 중'),
    faults: (faults || []).map((f) => ({ equipment_id: f.eq.equipment_id, code: f.eq.code, items: f.items })),
    waiting: waiting.map((e) => code(e.equipment_id)),
    held: (snap.coils || []).filter((c) => c.quality_status === 'hold').length,
    openItems: openItems.length,
  };
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
  S.outboxLabels = labels;
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
  $('obBack').onclick = goBack;
  const pane = $('obPane');
  pane.classList.remove('long-content');
  pane.innerHTML = '<p class="hint">불러오는 중…</p>';
  show('outbox');
  let list;
  try { list = (await getJson('/api/outbox/pending')).handovers || []; }
  catch (_) { pane.innerHTML = '<p class="hint">MES에서 대기 목록을 불러오지 못했습니다.</p>'; return; }
  pane.innerHTML = '<p class="hint">기기에 저장된 인계입니다. 클라우드 업로드를 기다리고 있습니다.</p>';
  if (!list.length) pane.insertAdjacentHTML('beforeend', '<p class="hint">대기 중인 인계가 없습니다.</p>');
  pane.classList.toggle('long-content', list.length > 2);
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

function homeEquipmentSummary(equipment, faults, available) {
  const ids = new Set(equipment.map(eq => eq.equipment_id));
  const abnormal = new Set((faults || []).filter(f => ids.has(f.eq.equipment_id)).map(f => f.eq.equipment_id)).size;
  return {total: equipment.length, normal: available ? equipment.length - abnormal : null, abnormal: available ? abnormal : null};
}
// 홈 생산 링 — 대시보드 정지 손실의 생산 링과 같은 그림(같은 좌표, 보이는 칸만 잘라 씀)
function renderHomeMade() {
  const box = $('homeMade'), v = S.an && lossView(S.an.production, S.an.loss);
  box.hidden = !(v && v.planned);
  if (box.hidden) return;
  const {cx, r} = LOSS_CHART.made, cy = LOSS_CHART.cy, pad = 12, f1 = (n) => n.toFixed(1) + '%';
  box.innerHTML = '<svg class="loss-chart made-only" viewBox="' + (cx - r - pad) + ' ' + (cy - r - pad) + ' ' + 2 * (r + pad) + ' ' + 2 * (r + pad)
    + '" role="img"><circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" class="made-base"/>'
    + madeRingArcs(v.planned, v.produced, v.slices).map((s) => '<path d="' + s.d + '" class="made-arc" style="stroke:' + s.color + '"/>').join('')
    + '<text x="' + cx + '" y="' + cy + '" text-anchor="middle" class="ctr">' + f1(v.producedPct) + '</text></svg>'
    + '<p><span>이번 주</span><b></b><span class="lost"></span></p>';
  box.querySelector('svg').setAttribute('aria-label', '이번 주 계획 ' + v.planned + '개 중 생산 ' + f1(v.producedPct));
  box.querySelector('b').textContent = v.produced.toLocaleString() + ' / ' + v.planned.toLocaleString() + '개';
  box.querySelector('.lost').textContent = '손실 ' + v.lost + '개';
}
function renderHomeWatch() {
  const box = $('homeWatch');
  const rows = S.an ? homeWatch(S.an) : [];
  box.hidden = !rows.length;
  S.homeWatchRows = rows;
  if (!rows.length) return;
  const span = (cls, text) => { const s = document.createElement('span'); s.className = cls; s.textContent = text; return s; };
  const h = document.createElement('p'); h.className = 'watch-h'; h.textContent = '지켜볼 설비';
  box.replaceChildren(h, ...rows.map((w) => {
    const b = document.createElement('button'); b.type = 'button'; b.className = 'watch-row';
    const lb = span('lb', w.label);
    if (w.unresolved) lb.appendChild(span('pill st miss', '원인 미확인'));
    // 좁은 칸: 윗줄 증상, 아랫줄 언제·효과 있던 조치
    const wq = S.equipment.find((e) => e.code === w.code), ec = span('eqc mono', w.code); if (wq) ec.prepend(eqChip(wq.equipment_id));
    b.append(ec, lb, span('meta', [w.meta, w.fix && '효과 있던 조치 ' + w.fix].filter(Boolean).join(' · ')));
    b.dataset.i = rows.indexOf(w);   // 누르면 그 증상의 지난 조치들(배선은 아래 DOM 블록 — openIncidents가 거기 있다)
    return b;
  }));
}
function renderHomeStatus() { renderHome(); }
/* 대시보드 정지 손실 보기 — 모든 %는 계획 생산량(정상이면 만들었을 양) 대비, 소수 한 자리.
 * 생산 % = 100 − 손실 %(합이 100이 되게). 설비마다 계획 대비 %(planPct)·색 종류(kind = 코드 앞부분).
 * 원형 조각은 6개까지(작은 조각은 구별이 안 된다): 손실 상위 5대는 설비 종류 색, 나머지는 회색 '기타' 한 조각.
 * 설비 줄의 표지 색(color)도 같은 규칙이라 링 조각과 줄이 맞는다. slices = 링에 그릴 조각. */
const RING_MAX = 5;
// 설비마다 하나의 색 — 종류 색(--hpu 등)을 먼저 쓰고, 같은 종류의 둘째 설비부터 새 색
const EQ_SPARE = ['#e0a96d', '#d98b8b', '#c9b458', '#7cc4d9'];
function eqColor(id) {
  if (!S.eqColors || !S.eqColors[id]) {
    if (!S.equipment.length) return 'var(--tx-3)';
    const used = new Set(); let spare = 0; S.eqColors = {};
    S.equipment.forEach((e) => {
      const k = ((e.code || '').split('-')[0] || 'pdp').toLowerCase();
      if (used.has(k)) S.eqColors[e.equipment_id] = EQ_SPARE[spare++ % EQ_SPARE.length];
      else { used.add(k); S.eqColors[e.equipment_id] = 'var(--' + k + ')'; }
    });
  }
  return S.eqColors[id] || 'var(--tx-3)';
}
function eqChip(id) { const c = document.createElement('i'); c.className = 'eqchip'; c.style.background = eqColor(id); return c; }
function lossView(production, loss) {
  const p = production || {planned: 0, lost: 0, produced: 0};
  const pct = (n) => p.planned ? Math.round(n / p.planned * 1000) / 10 : 0;
  const kind = (id) => (((S.equipment.find((e) => e.equipment_id === id) || {}).code || '').split('-')[0] || 'pdp').toLowerCase();
  const lostPct = pct(p.lost);
  let shown = 0;
  const rows = (loss || []).map((r) => {
    const top = r.coils > 0 && shown++ < RING_MAX;
    return {...r, kind: kind(r.equipment_id), planPct: pct(r.coils), color: top ? eqColor(r.equipment_id) : 'var(--tx-3)'};
  });
  const lossRows = rows.filter((r) => r.coils);
  const rest = lossRows.slice(RING_MAX).reduce((n, r) => n + r.coils, 0);
  const slices = [...lossRows.slice(0, RING_MAX).map((r) => ({equipment_id: r.equipment_id, coils: r.coils, color: r.color})),
    ...(rest ? [{equipment_id: null, coils: rest, color: 'var(--tx-3)'}] : [])];
  return {planned: p.planned, produced: p.produced, lost: p.lost, lostPct,
    producedPct: pct(p.produced), rows, slices};
}
/* 정지 손실 그림(SVG 하나): 왼쪽 생산 링, 오른쪽 손실 도넛 — 같은 크기(반지름·굵기), 같은 중심 높이(cy)에 나란히.
 * 손실 도넛 라벨은 조각 가운데 각도 바깥(labelR), 오른쪽 절반은 왼쪽 정렬·왼쪽 절반은 오른쪽 정렬.
 * 같은 쪽 라벨끼리 세로 간격이 gap보다 좁으면 아래로 민다. 왼쪽 라벨 시작(약 x 140)과 생산 링 오른쪽(x 129) 사이는 비운다. */
const LOSS_CHART = {w: 398, h: 190, cy: 95, gap: 16, minArc: 18, made: {cx: 66, r: 52}, loss: {cx: 264, r: 52, labelR: 76}};
const ringPt = (cx, cy, a, rad) => [cx + rad * Math.sin(a), cy - rad * Math.cos(a)];   // a: 12시 = 0, 시계 방향
function arcPath(cx, cy, r, a0, a1) {
  if (a1 - a0 >= 2 * Math.PI - 1e-9)   // 전부면 원 두 반쪽으로
    return 'M' + cx + ' ' + (cy - r) + ' A' + r + ' ' + r + ' 0 1 1 ' + cx + ' ' + (cy + r) + ' A' + r + ' ' + r + ' 0 1 1 ' + cx + ' ' + (cy - r);
  const [x0, y0] = ringPt(cx, cy, a0, r), [x1, y1] = ringPt(cx, cy, a1, r);
  return 'M' + x0.toFixed(1) + ' ' + y0.toFixed(1) + ' A' + r + ' ' + r + ' 0 ' + (a1 - a0 > Math.PI ? 1 : 0) + ' 1 ' + x1.toFixed(1) + ' ' + y1.toFixed(1);
}
// 생산 링: 회색 원 위에 끝부분(생산 다음부터 12시까지)을 설비별 손실 조각으로 — 계획 대비 실제 비율
function madeRingArcs(planned, produced, slices) {
  const {cx, r} = LOSS_CHART.made, cy = LOSS_CHART.cy;
  let at = planned ? 2 * Math.PI * produced / planned : 2 * Math.PI;
  return slices.map((s) => { const a0 = at; at += 2 * Math.PI * s.coils / planned; return {...s, d: arcPath(cx, cy, r, a0, at)}; });
}
function lossDonut(slices) {
  const total = slices.reduce((n, s) => n + s.coils, 0);
  if (!total) return [];
  const {cx, r, labelR} = LOSS_CHART.loss, cy = LOSS_CHART.cy;
  let at = 0;
  const out = slices.map((s) => {
    const a0 = at, a1 = at + 2 * Math.PI * s.coils / total; at = a1;
    const mid = (a0 + a1) / 2, [lx, ly] = ringPt(cx, cy, mid, labelR), [nx, ny] = ringPt(cx, cy, mid, r);
    // 손실 개수는 링 안(조각 가운데)에 — 조각 호가 숫자보다 짧으면(MIN_ARC px 미만) 바깥 라벨 옆으로
    const inside = r * (a1 - a0) >= LOSS_CHART.minArc;
    return {...s, d: arcPath(cx, cy, r, a0, a1), lx: Math.round(lx), ly: Math.round(ly), anchor: lx >= cx ? 'start' : 'end',
      nx: Math.round(nx), ny: Math.round(ny), inside};
  });
  ['start', 'end'].forEach((side) => {   // 같은 쪽 라벨 겹침 밀기
    const list = out.filter((o) => o.anchor === side).sort((p, q) => p.ly - q.ly);
    list.forEach((o, i) => { if (i && o.ly - list[i - 1].ly < LOSS_CHART.gap) o.ly = list[i - 1].ly + LOSS_CHART.gap; });
  });
  return out;
}
/* 홈 '지켜볼 설비' — 이번 교대에 다시 날 수 있는 것. ① '해결'로 닫았는데도 반복된 증상(원인 미확인) — 마지막 조치 뒤
 * 재발 기간(7일)을 넘겨 버틴 것(재발 없음)은 뺀다, ② 최근 조치해 아직 재발 기간 안인 증상, 최근 것 먼저.
 * 설비·증상당 한 줄, 최대 3줄. 누르면 그 증상의 지난 조치들. */
function homeWatch(a) {
  const code = (id) => (S.equipment.find((e) => e.equipment_id === id) || {}).code || id;
  const ids = (eq, al) => a.incidents.filter((x) => x.equipment_id === eq && x.alarm_code === al).map((x) => x.incident_id);
  const latest = (g) => a.incidents.find((x) => x.equipment_id === g.equipment_id && x.alarm_code === g.alarm_code) || {};
  // 같은 설비·증상에서 재발 없이 버틴 조치(카드 방법 먼저) — 다시 나면 먼저 해 볼 것
  const fix = (eq, al) => {
    const g = a.repeats.find((x) => x.equipment_id === eq && x.alarm_code === al);
    const ok = g ? (g.actions || []).filter((x) => x.held && !x.recurred) : [];
    ok.sort((x, y) => (y.method === 'card') - (x.method === 'card') || y.held - x.held);
    return ok[0] ? [ok[0].action, ...ok[0].card_ids].join(' · ') : '';
  };
  const rows = [], seen = new Set();
  a.repeats.filter((g) => g.resolved_recurred && latest(g).outcome !== 'held').forEach((g) => {
    seen.add(g.equipment_id + g.alarm_code);
    rows.push({code: code(g.equipment_id), label: g.label, meta: '4주 ' + g.count + '회', unresolved: true,
      fix: fix(g.equipment_id, g.alarm_code), incidents: g.incidents});
  });
  a.incidents.filter((i) => i.outcome === 'watching').forEach((i) => {   // incidents는 최근 경보가 먼저
    if (seen.has(i.equipment_id + i.alarm_code)) return;
    seen.add(i.equipment_id + i.alarm_code);
    const days = Math.floor((new Date(a.now) - new Date(i.recovered_at)) / 86400000);
    rows.push({code: code(i.equipment_id), label: i.label, meta: (days > 0 ? days + '일 전' : '오늘') + ' 조치', unresolved: false,
      fix: fix(i.equipment_id, i.alarm_code), incidents: ids(i.equipment_id, i.alarm_code)});
  });
  return rows.slice(0, 3);
}

const REPORT_DRAFT_KEY = 'shiftlink.report.draft';
function reportTargets(equipment, filter, faults, recent) {
  if (filter === 'fault') return equipment.filter((eq) => faults.some((f) => f.eq.equipment_id === eq.equipment_id));
  if (filter === 'recent') return equipment.filter((eq) => recent.includes(eq.code));
  return equipment;
}
function selectedReportPayload(draft, equipment) {
  const targets = equipment.filter((eq) => draft.ids.includes(eq.equipment_id));
  if (!targets.length) throw new Error('대상 장비를 선택해 주세요.');
  if (!draft.author.trim()) throw new Error('작성자를 입력해 주세요.');
  if (!draft.start || !draft.end || !Number.isFinite(Date.parse(draft.start)) || !Number.isFinite(Date.parse(draft.end)) || Date.parse(draft.end) < Date.parse(draft.start)) throw new Error('근무 시작·종료 시간을 확인해 주세요.');
  const records = draft.records || [];
  const names = (ids) => equipment.filter(eq => ids.includes(eq.equipment_id)).map(eq => eq.code).join(', ');
  const details = records.map((r,i) => {
    if (!r.equipment.length || r.equipment.some(id => !targets.some(eq => eq.equipment_id === id))) throw new Error('기록 '+(i+1)+': 대상 설비를 선택해 주세요.');
    if (!r.story.trim()) throw new Error('기록 '+(i+1)+': 상황·조치를 입력해 주세요.');
    if ((r.causes || []).some(c => c.equipment.some(id => !targets.some(eq => eq.equipment_id === id)))) throw new Error('기록 '+(i+1)+': 원인의 대상 설비를 확인해 주세요. 일지 대상에서 제외된 설비는 체크를 해제해 주세요.');
    return ['기록 '+(i+1)+' · '+r.type+' · '+names(r.equipment), r.story.trim(),
      ...(r.causes || []).map(c => '원인·조치 · '+names(c.equipment)+' · '+c.certainty+' · '+c.note),
      r.result !== null ? '결과·후속·인계: '+r.result : '', r.pms !== null ? 'PMS 계획 ID 메모: '+r.pms : '',
      r.candidate ? '지식카드 후보 · 별도 검토 필요' : ''].filter(Boolean).join('\n');
  });
  const memo = [draft.memo.trim(), ...details].filter(Boolean).join('\n\n') || '별도 작성 내용 없음';
  if (memo.length > 4000) throw new Error('전체 기록은 4000자 이내로 작성해 주세요.');
  return {kind:'work_log', memo_text:memo, equipment_id:targets.length === 1 ? targets[0].equipment_id : null,
    equipment_ids:targets.map((eq) => eq.equipment_id), attempts:[], observations:[],
    work_report:{records, legacy_memo:draft.memo, mes_context:draft.context},
    required_context:{author:draft.author.trim(), start_at:draft.start, end_at:draft.end,
      recipient_role:'다음 근무 담당자', timing:draft.start + ' ~ ' + draft.end, channel:'근무일지', acknowledgement:'인계 사항에서 읽음 확인',
      context:'대상 장비: ' + targets.map((eq) => eq.code).join(', ') + '\n' + draft.context}};
}
function reportDraft() {
  return {ids:S.reportSelected.slice(),memo:$('reportMemo').value,author:$('reportAuthor').value,start:$('reportStart').value,end:$('reportEnd').value,context:S.reportContext || '',records:S.reportRecords || []};
}
function saveReportDraft() {
  if(!S.reportDraftLoaded)return;
  try { localStorage.setItem(REPORT_DRAFT_KEY,JSON.stringify(reportDraft())); }
  catch (_) { $('reportStatus').textContent = '단말 초안 저장 실패 · 저장 전 화면을 닫지 마세요.'; }
}
function openReport() {
  S.reportInProgress=false;
  let keepIds=false;   // 아직 못 보낸 일지(전송 대기)를 다시 열 때만 그 대상 선택을 살린다
  try {
    const pending=JSON.parse(localStorage.getItem(HANDOVER_PENDING_KEY)||'null');
    keepIds=!!(pending && pending.kind==='work_log');
    const draft=pending && pending.kind==='work_log' ? {ids:pending.equipment_ids,memo:pending.work_report ? pending.work_report.legacy_memo : pending.memo_text,records:pending.work_report ? pending.work_report.records : [],author:pending.required_context.author,start:pending.required_context.start_at,end:pending.required_context.end_at,context:pending.required_context.context.replace(/^대상 장비: [^\n]*\n/,'')} : JSON.parse(localStorage.getItem(REPORT_DRAFT_KEY)||'null');
    if (draft) { S.reportSelected=(draft.ids||[]).filter((id)=>S.equipment.some((eq)=>eq.equipment_id===id)); S.reportContext=draft.context||''; S.reportRecords=draft.records||[];
      $('reportMemo').value=draft.memo||''; $('reportAuthor').value=draft.author||''; $('reportStart').value=draft.start||''; $('reportEnd').value=draft.end||''; }
  } catch (_) { $('reportStatus').textContent='초안을 읽지 못했습니다. 입력 내용을 확인해 주세요.'; }
  if (!S.reportRecords) S.reportRecords=[];
  if (!$('reportAuthor').value) $('reportAuthor').value=(S.operator && (S.operator.name||S.operator.id))||'';
  if (!keepIds) S.reportSelected=[];   // 화면에 들어올 때마다 지난 선택은 남기지 않는다(작성 중 내용은 그대로). 대상 다시 선택(reportEditTargets)은 이 함수를 거치지 않아 유지된다
  S.reportDraftLoaded=true;renderReportSelection(); show('reportSelect');
}
function openEquipmentReport() {
  openReport();
  if (!S.reportSelected.length && S.eq) {
    S.reportSelected=[S.eq.equipment_id];saveReportDraft();renderReportSelection();
  }
}
/* 지식 없음 답에서 「네」 — 현재 설비를 대상으로, 질문·답을 이상증상 기록 하나로 넣고 바로 작성 화면으로 간다. */
function reportFromChat(turn) {
  const eq=S.eq;if(!eq)return;
  openEquipmentReport();
  if(!S.reportSelected.includes(eq.equipment_id))S.reportSelected.push(eq.equipment_id);
  S.reportRecords.push({type:'이상증상',equipment:[eq.equipment_id],story:chatMemo(turn),causes:[],result:null,pms:null,candidate:false});
  saveReportDraft();enterReportWrite();
  // 직접 작성으로 들어왔으므로 중간 대상 선택 화면은 뒤로가기 이력에서 제외한다.
  if (navigationStack[navigationStack.length - 1] === 'reportSelect') navigationStack.pop();
}
function renderReportSelection() {
  const box=$('reportEquipment'); box.replaceChildren();
  const visible=reportTargets(S.equipment,S.reportFilter,S.faults||[],recentMaintenanceCodes());
  visible.forEach((eq)=>{
    const tr=document.createElement('tr');
    const checkCell=document.createElement('td');const label=document.createElement('label');const check=document.createElement('input');check.type='checkbox';check.checked=S.reportSelected.includes(eq.equipment_id);check.setAttribute('aria-label',eq.code+' 선택');
    check.onchange=()=>{S.reportSelected=check.checked?[...new Set([...S.reportSelected,eq.equipment_id])]:S.reportSelected.filter((id)=>id!==eq.equipment_id);saveReportDraft();renderReportSelection();};
    label.appendChild(check);checkCell.appendChild(label);
    const code=document.createElement('td');code.textContent=eq.code+' · '+eq.group;code.prepend(eqChip(eq.equipment_id));
    const status=document.createElement('td');const badge=document.createElement('span');const fault=(S.faults||[]).some((f)=>f.eq.equipment_id===eq.equipment_id);badge.className='pill '+(fault?'miss':'status-done');badge.textContent=S.snapshot&&S.online!==false?(fault?'조치 필요':'정상'):'연결 확인 필요';status.appendChild(badge);tr.append(checkCell,code,status);box.appendChild(tr);
  });
  if (!visible.length) { const tr=document.createElement('tr'); const td=document.createElement('td');td.colSpan=3;td.textContent='해당 조건의 장비가 없습니다.';tr.appendChild(td);box.appendChild(tr); }
  const selected=visible.filter((eq)=>S.reportSelected.includes(eq.equipment_id)).length;
  $('reportSelectAll').checked=visible.length>0&&selected===visible.length;$('reportSelectAll').indeterminate=false;$('reportSelectAll').disabled=!visible.length;
  $('reportCount').textContent='선택 '+S.reportSelected.length+'대';$('reportWrite').disabled=!S.reportSelected.length;
  [['reportFilterAll','all'],['reportFilterFault','fault'],['reportFilterRecent','recent']].forEach(([id,filter])=>{$(id).classList.toggle('primary',filter===S.reportFilter);$(id).setAttribute('aria-pressed',String(filter===S.reportFilter));});
  $('reportFilterRecent').textContent=S.reportFilter==='recent'?'전체 설비':'최근 정비 설비';
}
function recentMaintenanceCodes() {
  return [...new Set(allHandovers().filter(h=>h.kind!=='work_log'||(h.work_report?.records||[]).some(r=>['고장·정비','PMS 정비'].includes(r.type))).filter(h=>Date.parse(h.created_at||h.shift_date)>=Date.now()-7*86400000).flatMap(h=>handoverEquipment(h,S.equipment).map(eq=>eq.code)))];
}
const SHIFT_HOURS={A:'08:00 - 16:00',B:'16:00 - 24:00',C:'00:00 - 08:00'};
function shiftAt(now = new Date()) {
  const local=new Date(now.toLocaleString('en-US',{timeZone:'Asia/Seoul'}));
  return {date:local.getFullYear()+'-'+String(local.getMonth()+1).padStart(2,'0')+'-'+String(local.getDate()).padStart(2,'0'),code:local.getHours()<8?'C':local.getHours()<16?'A':'B'};
}
function syncReportShift() {
  const date=$('reportWorkDate').value,code=$('reportShift').value;
  if (!date || !['A','B','C'].includes(code)) return;
  const start={A:'08:00',B:'16:00',C:'00:00'}[code],end={A:'16:00',B:'00:00',C:'08:00'}[code];
  const next=new Date(date+'T12:00:00Z');if(code==='B')next.setUTCDate(next.getUTCDate()+1);
  $('reportStart').value=date+'T'+start;$('reportEnd').value=next.toISOString().slice(0,10)+'T'+end;
  saveReportDraft();
}
// 이전 기록 = 지난번에 쓰다 남긴 내용(자유 입력·추가 기록·불러온 센서값). 있으면 불러올지 묻고, 없으면 바로 보여 준다.
// 전송 대기 중인 일지(다시 보내기)와, 같은 작성 중 '대상 다시 선택'으로 돌아온 경우는 묻지 않는다.
function hasPreviousReport() {
  return !!($('reportMemo').value || S.reportContext || (S.reportRecords || []).length);
}
function resetReportForm() {   // 새로 작성: 기본값이 있는 칸(날짜·근무시간·작성자)만 남기고 비운다
  S.reportRecords=[];S.reportContext='';
  $('reportMemo').value='';$('reportStart').value='';$('reportEnd').value='';
  $('reportAuthor').value=(S.operator && (S.operator.name||S.operator.id))||'';
  $('reportStatus').textContent='';
}
function openReportWrite() {
  let pending=null;try{pending=JSON.parse(localStorage.getItem(HANDOVER_PENDING_KEY)||'null');}catch(_){}
  if (!S.reportInProgress && !(pending&&pending.kind==='work_log') && hasPreviousReport()) { $('reportResume').showModal();$('reportResume').focus();return; }
  enterReportWrite();
}
function enterReportWrite() {
  S.reportInProgress=true;
  const current=shiftAt(),saved=$('reportStart').value;
  $('reportWorkDate').value=saved?saved.slice(0,10):current.date;
  const hour=saved?Number(saved.slice(11,13)):null;
  $('reportShift').value=hour===null?current.code:hour<8?'C':hour<16?'A':'B';
  let pending=null;try{pending=JSON.parse(localStorage.getItem(HANDOVER_PENDING_KEY)||'null');}catch(_){}
  const retry=!!(pending&&pending.kind==='work_log');
  $('reportWorkDate').disabled=retry;$('reportShift').disabled=retry;$('reportPendingShift').hidden=!retry;
  if(retry){
    $('reportPendingShift').textContent='전송 대기 · '+$('reportStart').value.slice(11,16)+'–'+$('reportEnd').value.slice(11,16);$('reportShift').value='pending';
  }else syncReportShift();
  $('reportTargets').textContent=S.equipment.filter((eq)=>S.reportSelected.includes(eq.equipment_id)).map((eq)=>eq.code).join(' · ');
  $('reportDate').textContent=new Date().toLocaleDateString('ko-KR');renderReportRecords();saveReportDraft();show('reportWrite');
}

function renderReportRecords() {
  const records=S.reportRecords||[];
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const eqChecks=(ids,index,causeIndex)=>'<div class="eq-list">'+S.equipment.filter(eq=>S.reportSelected.includes(eq.equipment_id)||ids.includes(eq.equipment_id)).map(eq=>'<label class="check"><input type="checkbox" data-eq="'+esc(eq.equipment_id)+'" data-record="'+index+'" '+(causeIndex!==undefined?'data-cause="'+causeIndex+'"':'')+' '+(ids.includes(eq.equipment_id)?'checked':'')+'>'+esc(eq.code)+' '+esc(eq.group||'')+(S.reportSelected.includes(eq.equipment_id)?'':' (일지 대상에서 제외됨)')+'</label>').join('')+'</div>';
  const edit=(value,key,index,placeholder,ci)=>'<textarea aria-label="'+placeholder+'" class="edit" data-key="'+key+'" data-record="'+index+'" '+(ci!==undefined?'data-cause="'+ci+'"':'')+' maxlength="4000" placeholder="'+placeholder+'">'+esc(value)+'</textarea>';
  $('reportLegacy').hidden=!$('reportMemo').value;
  $('reportMes').textContent=S.reportContext||'센서값을 불러오면 원본 값·단위·관측 시각이 표시됩니다. 미수신 값은 — 입니다.';
  $('reportRecords').innerHTML=records.length?records.map((r,i)=>'<section class="record" aria-label="추가 기록 '+(i+1)+'"><div class="record-head"><strong>기록 '+String(i+1).padStart(2,'0')+'</strong><select data-key="type" data-record="'+i+'" aria-label="기록 구분">'+['추가 기록','이상증상','고장·정비','PMS 정비'].map(t=>'<option '+(r.type===t?'selected':'')+'>'+t+'</option>').join('')+'</select><span class="sp"></span><button type="button" class="smallbtn" data-action="remove" data-record="'+i+'">기록 삭제</button></div><table><tbody><tr><th>대상 설비 *</th><td>'+eqChecks(r.equipment,i)+'</td></tr><tr><th>상황·조치 *</th><td>'+edit(r.story,'story',i,'어떤 상황이었고, 어떤 조치를 했는지 적습니다.')+'</td></tr>'+(r.causes.length?'<tr><th>확인한 원인</th><td>'+r.causes.map((c,ci)=>'<div class="cause-row">'+(c.equipment.length===1?'<div class="cause-eq">'+esc(((S.equipment.find(e=>e.equipment_id===c.equipment[0])||{}).code)||c.equipment[0])+' '+esc((S.equipment.find(e=>e.equipment_id===c.equipment[0])||{}).group||'')+'</div>':'<div class="checks">'+eqChecks(c.equipment,i,ci)+'</div>')+'<select aria-label="원인 확인 상태" data-record="'+i+'" data-cause="'+ci+'" data-key="certainty">'+['추정','확인','배제'].map(t=>'<option '+(c.certainty===t?'selected':'')+'>'+t+'</option>').join('')+'</select>'+edit(c.note,'note',i,'원인·해당 조치·확인 근거',ci)+'</div>').join('')+'</td></tr>':'')+(r.result!==null?'<tr><th>결과·후속·인계<br><small>선택 기록</small></th><td>'+edit(r.result,'result',i,'조치 결과나 다음 근무자에게 전달할 내용')+'</td></tr>':'')+(r.pms!==null?'<tr><th>PMS 계획 ID</th><td>'+edit(r.pms,'pms',i,'참고할 PMS 계획 ID (메모로 보관)')+'</td></tr>':'')+'</tbody></table><div class="record-end"><button data-action="cause" data-record="'+i+'">＋ 원인·조치 추가</button>'+(r.result===null?'<button data-action="result" data-record="'+i+'">＋ 결과·인계</button>':'')+(r.pms===null?'<button data-action="pms" data-record="'+i+'">＋ PMS 연결</button>':'')+'<label class="check"><input type="checkbox" data-key="candidate" data-record="'+i+'" '+(r.candidate?'checked':'')+'>지식카드 후보</label></div></section>').join(''):'<table aria-label="특이사항 미작성"><tbody><tr><td class="empty"><span>특이사항 기록란</span><p>별도 작성 내용 없음</p></td></tr></tbody></table>';
}
function addReportRecord() {
  if (!S.reportRecords) S.reportRecords=[];
  S.reportRecords.push({type:'추가 기록',equipment:[],story:'',causes:[],result:null,pms:null,candidate:false});
  renderReportRecords();saveReportDraft();
  $('reportRecords').lastElementChild?.scrollIntoView({block:'start'});
}

async function importReportMes() {
  $('reportImport').disabled=true;
  try { const [snap,log]=await Promise.all([getJson('/api/state'),getJson('/api/events')]);
    S.reportContext=reportMesContext(snap,log.events,S.equipment.filter((eq)=>S.reportSelected.includes(eq.equipment_id)));
    $('reportMes').textContent=S.reportContext;
    $('reportStatus').textContent='선택 장비의 센서값을 첨부했습니다.';saveReportDraft();
  } catch(err) { $('reportStatus').textContent='센서값을 불러오지 못했습니다. '+err.message; }
  finally { $('reportImport').disabled=false; }
}
async function openReportArchive() {
  const session=++reportArchiveSession;reportArchiveRequest++;
  const dialog=$('reportArchive');
  $('reportArchiveList').replaceChildren();$('reportArchiveDetail').textContent='';
  $('reportArchiveStatus').textContent='DB에서 일지를 불러오는 중…';dialog.showModal();
  try {
    const {reports}=await getJson('/api/work-reports?limit=30');
    if(session!==reportArchiveSession||!dialog.open)return;
    for(const report of reports){
      const button=document.createElement('button');button.type='button';
      const context=report.required_context||{};
      button.textContent=(context.start_at||report.created_at)+' · '+(context.author||'미기재');
      button.addEventListener('click',()=>loadReportArchiveDetail(report.handover_id));
      $('reportArchiveList').appendChild(button);
    }
    $('reportArchiveStatus').textContent=reports.length?'조회할 일지를 선택하세요.':'저장된 근무일지가 없습니다.';
  }catch(err){if(session===reportArchiveSession&&dialog.open)$('reportArchiveStatus').textContent='일지를 불러오지 못했습니다. '+err.message;}
}
let reportArchiveRequest=0,reportArchiveSession=0;
async function loadReportArchiveDetail(id) {
  const request=++reportArchiveRequest;
  $('reportArchiveDetail').textContent='';$('reportArchiveStatus').textContent='일지를 불러오는 중…';
  try {
    const {report}=await getJson('/api/work-reports/'+encodeURIComponent(id));
    if(request!==reportArchiveRequest||!$('reportArchive').open)return;
    const context=report.required_context||{};
    const status={pending:'중앙 DB 업로드 대기',uploaded:'중앙 DB 업로드 완료',conflict:'중앙 DB 충돌 확인 필요'};
    $('reportArchiveDetail').textContent=[context.start_at+' ~ '+context.end_at, '작성자: '+context.author,
      report.memo_text, report.work_report ? report.work_report.mes_context : context.context].filter(Boolean).join('\n\n');
    $('reportArchiveStatus').textContent='DB 저장 확인 · '+report.handover_id+' · '+(status[report.status]||report.status);
  }catch(err){if(request===reportArchiveRequest&&$('reportArchive').open)$('reportArchiveStatus').textContent='일지를 불러오지 못했습니다. '+err.message;}
}

async function saveReport() {
  $('reportSave').disabled=true;
  try { const note=selectedReportPayload(reportDraft(),S.equipment);const result=await submitHandover(note, (_path,init)=>api('/api/work-reports',init));
    localStorage.removeItem(REPORT_DRAFT_KEY);S.reportDraftLoaded=false;S.reportSelected=[];S.reportContext='';S.reportRecords=[];$('reportMemo').value='';
    $('reportStatus').textContent='MES 로컬 저장 완료 · '+result.handover_id; await refreshSavedHandovers();show('home');
  } catch(err) { $('reportStatus').textContent='저장 확인 실패 · '+err.message+' · 입력 내용은 유지됩니다.';saveReportDraft(); }
  finally { $('reportSave').disabled=false; }
}

// Node 테스트는 DOM 없이 순수 함수만 쓴다.
// 임계값·통과 장수는 서버 /api/face/config 와 프레임 응답이 준다. 여기 숫자는 두지 않는다.
function faceVerdict(scores, threshold, need, max) {
  const passed = scores.filter((score) => score >= threshold).length;
  if (passed >= need) return 'pass';
  if (scores.length >= max) return 'fail';
  return 'wait';
}

if (typeof module !== 'undefined') { module.exports = { equipmentGroups, handoverEquipment, dutyTimeline, reportTargets, selectedReportPayload, homeEquipmentSummary, homeWatch, lossView, lossDonut, madeRingArcs, unityLocation, handoverStatus, mesHandoverContext, appendMesContext, dashSummary, S, equipmentFrom, stateOf, usableReadings, evalCondition, rankCards, cardFits, obsView, queryApiPayload, responseCards, scanTarget, staleResponse, submitHandover, outboxLabels, refreshOutbox, outboxItemView, equipmentFromLink, symptomsFor, alertOrder, releaseContext, alertTarget, failScan, hangulPress, hangulText, emptyHangul, faceVerdict, stopFaceCamera, safetyAlert, answerBody, chatMemo, riskyAction, mesSummary, resolveError, sessionPayload, draftNotice, actionChips }; }
if (typeof document !== 'undefined') {

// ── 배선 ───────────────────────────────────────────────────────────
function on(id, fn) { const el = $(id); if (el) el.addEventListener('click', /Back$|^(scanClose|manualClose)$/.test(id)?goBack:fn); }

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
  const name = $('loginId').value.trim();
  const id = $('loginId').value.trim();
  if (!name || !id) {
    loginError('사번을 입력하세요.');
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
      setFaceStatus('fail', '얼굴이 안 보입니다');
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
        setFaceStatus('fail', '얼굴 인식이 안 됐습니다');
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
  $('faceWho').textContent = '사번 : ' + S.operator.id;
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
on('faceBack', () => show('faceSetup'));
on('faceRetry', () => { startFaceCamera(); });
on('faceBypass', enterWork);
on('pdaExit', () => { try { sessionStorage.removeItem(OPERATOR_KEY); } catch (_) {} fetch('/api/pda/exit', { method: 'POST' }).catch(() => {}); });
document.querySelectorAll('.home').forEach((b) => b.addEventListener('click', () => show('home')));
on('toScan', startScan);
on('scanClose', () => show('home'));
on('scanManual', openManual);
on('scanShoot', shootScan);
on('toManual', openManual);
on('chatCancel', () => { const t = S.chat.find(turn => turn.status === 'pending'); if (!t) return; t.status = 'cancelled'; renderChat(); renderSymptoms(); renderAskBlock(); });
on('homeWarnings', event => { const button = event.target.closest('button[data-equipment-id]'); if (!button) return; const f = (S.faults || []).find(f => f.eq.equipment_id === button.dataset.equipmentId); if (f) openAlertGo({equipment_id:f.eq.equipment_id,items:f.items.slice()}); });
on('toChat', () => { if (S.eq) $('toAsk').click(); else openManual(); });
on('manualClose', () => show(S.eq ? 'ctx' : 'home'));
on('manualToScan', startScan);
on('ctxBack', () => show('home'));
on('ctxEdit', startScan);
on('toAsk', () => { renderSymptoms(); renderObsList(); renderAskBlock(); show('chat'); loadMesObservations(); });
on('obsReload', () => loadMesObservations());
on('mesRefresh', async () => { await loadMesObservations(); S.sensorSnapshot = null; renderEquipmentMetrics(); });
on('askBack', () => show('ctx'));
on('doSearch', () => sendChat(currentQuestion()));
on('suggToggle', () => { S.suggOpen = !S.suggOpen; renderSymptoms(); });
on('triesBack', () => show('chat'));
on('toHandover', openHistory);
on('toHandoverHome', openHandover);   // 전체 인계 — 선택 설비로 거르지 않는다
on('homePending', openOutbox);
on('hoPending', openOutbox);
on('hoBack', () => show(S.hoBack || (S.eq ? 'ctx' : 'home')));   // 홈 목록에서 왔으면 홈으로
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
      attempts:S.tries, observations:S.observations,
      ...(S.resolution ? {resolution: S.resolution} : {})});
    haptic([120]);
    $('hoWarn').textContent = 'MES 로컬 저장 완료 · ' + result.handover_id
      + (result.draft ? ' · ' + draftNotice(result.draft) : '');
    S.resolution = null;
    refreshSavedHandovers(); pollOutbox();   // 저장 즉시 '업로드 대기' 반영 — 다음 주기까지 기다리지 않는다
  } catch (err) {
    $('hoWarn').textContent = '저장 확인 실패 · ' + err.message + ' · 같은 메모로 다시 저장하면 재전송됩니다.';
    $('hoSave').disabled = false;
  }
});
['hoMemo','hoCtx','hoRole','hoTiming','hoChannel','hoAck'].forEach((id) => {
  $(id).addEventListener('input', validateHandover);
});
on('resBack', () => show('chat'));
on('resAddCustom', () => {
  const text = $('resCustom').value.trim();
  if (!text || !S.res) return;
  S.res.live = {action: text, lockout: null}; $('resCustom').value = ''; renderResolve();
});
on('resFinish', finishResolve);
on('resMore', () => { if (S.res) { S.res.phase = 'work'; renderResolve(); } });
$('resSymptom').addEventListener('input', () => { if (S.res) S.res.symptom = $('resSymptom').value; });
$('resCauseCustom').addEventListener('input', () => { if (S.res) { S.res.causeCustom = $('resCauseCustom').value; renderResolve(); } });
on('resSave', () => {
  const r = S.res;
  if (!r) return;
  r.symptom = $('resSymptom').value;
  const err = resolveError(r);
  resolveWarn(err);
  if (err) return;
  openHandoverNew(chatMemo(r.turn));
  S.resolution = sessionPayload(r);   // openHandoverNew가 비운 뒤에 붙인다
  S.hoNewBack = 'resolve';
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


// Deployed chat, camera and resolution handlers stay intact in the new layout.
Array.from(document.querySelector('#s-chat').children).filter((el)=>!el.classList.contains('appbar')).forEach((el)=>$('chatPanel').appendChild(el));
on('navigationBack',goBack);on('faceSetupReturn',goBack);
['reportWorkDate','reportShift'].forEach(id=>$(id).addEventListener('change',syncReportShift));
window.addEventListener('resize',()=>{if(S.screen==='manual')layoutManualList();});
[['expandEquipment','equipment-only'],['expandChat','chat-only'],['splitWorkspace','']].forEach(([id,mode])=>on(id,()=>{const w=$('equipmentWorkspace');w.classList.remove('equipment-only','chat-only');if(mode)w.classList.add(mode);['expandEquipment','expandChat','splitWorkspace'].forEach(button=>$(button).setAttribute('aria-pressed',String(button===id)));}));
const divider=document.querySelector('.workspace-divider');
function resizeWorkspace(percent){const w=$('equipmentWorkspace');const n=Math.max(25,Math.min(75,percent));w.style.setProperty('--equipment-width',n+'fr');w.style.setProperty('--chat-width',(100-n)+'fr');divider.setAttribute('aria-valuenow',Math.round(n));}
divider.setAttribute('aria-valuemin','25');divider.setAttribute('aria-valuemax','75');divider.setAttribute('aria-valuenow','60');
divider.addEventListener('pointerdown',event=>{divider.setPointerCapture(event.pointerId);});
divider.addEventListener('pointermove',event=>{if(!divider.hasPointerCapture(event.pointerId))return;const r=$('equipmentWorkspace').getBoundingClientRect();resizeWorkspace((event.clientX-r.left)/r.width*100);});
divider.addEventListener('keydown',event=>{if(['ArrowLeft','ArrowRight'].includes(event.key)){event.preventDefault();resizeWorkspace(Number(divider.getAttribute('aria-valuenow'))+(event.key==='ArrowRight'?5:-5));}});
on('toggleChat', () => setSensorsOpen(!S.sensorsOpen));
on('toDutyHandover',openHandover);on('toEquipmentReport',openEquipmentReport);
on('toDashboard',openDashboard);on('dashboardBack',()=>show('home'));on('historyBack',()=>show('ctx'));
on('toReport',openReport);on('reportBack',()=>show('home'));on('reportEditTargets',()=>{saveReportDraft();renderReportSelection();show('reportSelect');});on('reportWrite',openReportWrite);on('reportSave',()=>$('reportSaveConfirm').showModal());on('reportSaveYes',()=>{$('reportSaveConfirm').close();saveReport();});on('reportSaveNo',()=>$('reportSaveConfirm').close());on('reportImport',importReportMes);
[['reportFilterAll','all'],['reportFilterFault','fault'],['reportFilterRecent','recent']].forEach(([id,filter])=>on(id,()=>{S.reportFilter=filter==='recent'&&S.reportFilter==='recent'?'all':filter;renderReportSelection();}));
$('reportSelectAll').addEventListener('change',(event)=>{const visible=reportTargets(S.equipment,S.reportFilter,S.faults||[],recentMaintenanceCodes()).map((eq)=>eq.equipment_id);S.reportSelected=event.target.checked?[...new Set([...S.reportSelected,...visible])]:S.reportSelected.filter((id)=>!visible.includes(id));saveReportDraft();renderReportSelection();});

on('reportArchiveOpen',openReportArchive);
on('reportArchiveClose',()=>$('reportArchive').close());
$('reportArchive').addEventListener('close',()=>{reportArchiveRequest++;reportArchiveSession++;});
on('reportAdd',addReportRecord);
$('reportRecords').addEventListener('input',event=>{
  const t=event.target;if(t.dataset.record===undefined)return;
  const r=S.reportRecords[Number(t.dataset.record)];
  const target=t.dataset.cause!==undefined?r.causes[Number(t.dataset.cause)]:r;
  if(t.dataset.eq){const ids=new Set(target.equipment);t.checked?ids.add(t.dataset.eq):ids.delete(t.dataset.eq);target.equipment=[...ids];}
  if(t.dataset.key)target[t.dataset.key]=t.type==='checkbox'?t.checked:t.value;
  saveReportDraft();
});
$('reportRecords').addEventListener('click',event=>{
  const b=event.target.closest('button[data-action]');if(!b)return;
  const index=Number(b.dataset.record);
  const r=S.reportRecords[index];
  if(b.dataset.action==='remove'){
    if(!window.confirm('기록 '+(index+1)+'을 삭제할까요?'))return;
    S.reportRecords.splice(index,1);
  }
  if(b.dataset.action==='cause'){const have=new Set(r.causes.flatMap(c=>c.equipment));const todo=r.equipment.filter(id=>!have.has(id));(todo.length?todo:[null]).forEach(id=>r.causes.push({equipment:id?[id]:[],certainty:'추정',note:''}));}
  if(b.dataset.action==='result')r.result='';
  if(b.dataset.action==='pms')r.pms='';
  renderReportRecords();saveReportDraft();
});

['reportMemo','reportAuthor','reportStart','reportEnd'].forEach((id)=>$(id).addEventListener('input',saveReportDraft));
on('reportResumeLoad',()=>{$('reportResume').close();enterReportWrite();});on('reportResumeNew',()=>{$('reportResume').close();resetReportForm();enterReportWrite();});on('notifyBell',toggleNotify);on('notifyFloat',toggleNotify);on('logout',()=>{$('logoutConfirm').showModal();$('logoutConfirm').focus();});on('logoutNo',()=>$('logoutConfirm').close());on('logoutYes',()=>{$('logoutConfirm').close();saveReportDraft();stopFaceCamera();stopUnityCamera();releaseContext(S);S.operator=null;S.linkedEquipment=null;try{sessionStorage.removeItem(OPERATOR_KEY);}catch(_){}renderContext();$('employeePassword').value='';show('login');});
on('accountOpen',()=>show('account'));on('accountBack',()=>show('login'));on('faceOpen',()=>show('faceSetup'));on('accountFace',()=>show('faceSetup'));on('faceSetupBack',()=>show('login'));
$('accountForm').addEventListener('submit',async(event)=>{
  event.preventDefault();if($('accountSubmit').disabled)return;
  $('accountSubmit').disabled=true;
  try {
    const res=await api('/api/account/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:$('employeeId').value.trim(),password:$('employeePassword').value})});
    const data=await res.json();
    if(!res.ok)throw Error(data.error||'로그인하지 못했습니다.');
    S.operator=data.operator;$('employeePassword').value='';$('accountMessage').textContent='';enterWork();
  } catch(err){$('employeePassword').value='';$('accountMessage').textContent=err.message;}
  finally{$('accountSubmit').disabled=false;}
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
      .forEach((d) => items.push(d.symptom));
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

// 알림 — 헤더 종 + 미확인 배지 + 눌러 여는 목록. 미확인 = 아직 '확인'하지 않은 이상(같은 설비의 내용이 바뀌면 다시 미확인).
const ackOf = () => (S.alertAck = S.alertAck || {});
const ackKey = (f) => f.items.join('|');
const unacked = (faults) => faults.filter((f) => ackOf()[f.eq.equipment_id] !== ackKey(f));
function renderAlert(faults) {
  S.faults = faults;
  const un = unacked(faults).length;
  const view = faults.map((f) => f.eq.code + ackKey(f) + (ackOf()[f.eq.equipment_id] === ackKey(f))).join('|') + '@' + (S.eq ? S.eq.code : '');
  if (view === S.alertView) return;   // 내용이 같으면 다시 그리지 않는다 — 누르는 도중 다시 그리면 클릭이 사라진다.
  S.alertView = view;
  if (un > (S.alertUn || 0)) { haptic([80, 60, 80]); notifyBubble(un); }
  S.alertUn = un;
  paintNotify();
}
function notifyBubble(n) {
  document.querySelectorAll('.notify-bubble').forEach((el) => { el.textContent = '미확인 알림 ' + n + '건'; el.hidden = false; });
  clearTimeout(S.bubbleT);
  S.bubbleT = setTimeout(() => document.querySelectorAll('.notify-bubble').forEach((el) => { el.hidden = true; }), 6000);
}
function paintNotify() {
  const un = unacked(S.faults || []).length;
  document.querySelectorAll('.notify').forEach((btn) => {
    const c = btn.querySelector('.notify-count');
    btn.classList.toggle('on', un > 0);
    c.hidden = !un; c.textContent = un > 99 ? '99+' : String(un);
    btn.setAttribute('aria-label', '알림, 미확인 ' + un + '건');
  });
  if (!$('notifyPanel').hidden) renderNotifyPanel();
}
function closeNotify() {
  $('notifyPanel').hidden = true;
  document.querySelectorAll('.notify').forEach((btn) => btn.setAttribute('aria-expanded', 'false'));
}
function toggleNotify() {
  const p = $('notifyPanel'), open = p.hidden;
  p.hidden = !open;
  document.querySelectorAll('.notify').forEach((btn) => btn.setAttribute('aria-expanded', String(open)));
  document.querySelectorAll('.notify-bubble').forEach((el) => { el.hidden = true; });
  if (open) renderNotifyPanel();
}
function renderNotifyPanel() {
  const p = $('notifyPanel'), faults = alertOrder(S.faults || [], S.eq), un = unacked(faults).length;
  p.innerHTML = '<header><h2></h2><button type="button" class="np-all">모두 확인</button><button type="button" class="np-x" aria-label="닫기">✕</button></header><div class="np-list"></div>';
  p.querySelector('h2').textContent = un ? '미확인 알림 ' + un + '건' : faults.length ? '미확인 알림 없음' : '알림 없음';
  const all = p.querySelector('.np-all'); all.disabled = !un;
  all.addEventListener('click', () => { faults.forEach((f) => { ackOf()[f.eq.equipment_id] = ackKey(f); }); S.alertUn = 0; S.alertView = null; paintNotify(); });
  p.querySelector('.np-x').addEventListener('click', closeNotify);
  const list = p.querySelector('.np-list');
  faults.forEach((f) => {
    const acked = ackOf()[f.eq.equipment_id] === ackKey(f), row = document.createElement('div');
    row.className = 'np-row' + (f.level === 0 ? '' : ' warn') + (acked ? ' acked' : '');
    row.innerHTML = '<i class="np-dot"></i><div><div class="np-head"><span class="np-tag"></span><b class="np-code mono"></b><span class="np-at"></span></div><p class="np-msg"></p></div><button type="button" class="np-go">설비 확인</button>';
    row.querySelector('.np-tag').textContent = f.level === 0 ? '고장' : '주의';
    row.querySelector('.np-code').textContent = f.eq.code;
    row.querySelector('.np-at').textContent = f.at ? new Date(f.at).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }) + ' 발생' : '';
    row.querySelector('.np-msg').textContent = f.items.join(' · ');
    // 설비를 바로 바꾸지 않는다 — 확인 화면에서 code를 크게 보이고 하단 버튼으로만 확정한다(B3·A4).
    row.querySelector('.np-go').addEventListener('click', () => {
      ackOf()[f.eq.equipment_id] = ackKey(f); S.alertUn = unacked(S.faults).length; S.alertView = null; closeNotify(); paintNotify();
      openAlertGo({ equipment_id: f.eq.equipment_id, items: f.items.slice() });
    });
    list.appendChild(row);
  });
}
document.addEventListener('click', (e) => {
  if ($('notifyPanel').hidden || e.target.closest('#notifyPanel, .notify')) return;
  closeNotify();
});

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


function renderDash() {
  if (!S.snap) return;
  const d = dashSummary(S.snap, S.equipment, S.handovers, S.faults);
  renderHomeStatus();
  loadAnalytics(false);   // 홈 생산 링·지켜볼 설비, 대시보드 분석(10초에 한 번)
  // 이번 교대에 처리할 일 — 0이면 숨긴다(이상 설비는 홈 이상 칸에 이미 있다)
  const todo = [d.waiting.length ? '연쇄 정지 ' + d.waiting.join(', ') : '', d.held ? '제품 보류 코일 ' + d.held : ''].filter(Boolean);
  const tb = $('homeTodo');
  tb.hidden = !todo.length;
  $('homeWatch').classList.toggle('todo', todo.length > 0);
  tb.replaceChildren(...todo.map((t) => { const s = document.createElement('span'); s.className = 'pill'; s.textContent = t; return s; }));
  if (S.screen !== 'dashboard') return;
  const line = $('dashLine');
  line.textContent = d.line;
  // 화면 낭독기용 알림 — 이상·후속 대기 수가 바뀔 때만 글자를 바꾼다(시계처럼 매번 바뀌는 글자는 읽히지 않게)
  const alertText = '이상 ' + d.faults.length + '대 · 연쇄 정지 ' + d.waiting.length + '대';
  if ($('dashAlert').textContent !== alertText) $('dashAlert').textContent = alertText;
  line.className = 'dash-line ' + (d.faults.length || d.mode === 'quality_hold' ? 'warn' : d.mode === 'running' ? 'run' : '');
  const tile = (id, cls, n, title, desc) => {
    const el = $(id); el.className = 'dash-tile ' + cls; el.innerHTML = '<span class="n"></span><span class="t"></span><p class="d"></p>';
    el.querySelector('.n').textContent = n; el.querySelector('.t').textContent = title; el.querySelector('.d').textContent = desc;
    return el;
  };
  tile('dashFaults', d.faults.length ? 'bad' : '', d.faults.length, '이상 설비', d.faults.length ? '' : '이상 설비 없음');
  tile('dashWaiting', d.waiting.length ? 'warn' : '', d.waiting.length, '연쇄 정지 설비', d.waiting.length ? d.waiting.join(', ') : '없음');
  tile('dashHeld', d.held ? 'warn' : '', d.held, '제품 보류 코일', d.held ? '' : '없음');
}

// 홈 '상세 보기' → 대시보드(Depth 1): 라인 상태 한 줄 + 분석 4칸(정지 손실·반복 증상·조치 효과·지식 공백)
function openDashboard() { show('dashboard'); renderDash(); if (S.an) renderAnalytics(); loadAnalytics(true); }   // 받아 둔 값이 있으면 먼저 그린다
/* 대시보드 분석 — /api/analytics(저장 이력 + 이 실행의 사건). 계산은 서버(analytics.py), 화면은 숫자와 근거 사건만. */
const AN_OUTCOME = { recurred: ['재발', 'miss'], watching: ['관찰 중', 'unknown'], held: ['재발 없음', 'match'], open: ['조치 중', 'miss'] };
const AN_RESULT = { resolved: '해결', temporary: '임시 조치', failed: '실패' };
const AN_REFRESH_MS = 10000;
const eqCode = (id) => (S.equipment.find((e) => e.equipment_id === id) || {}).code || id;
const mdhm = (iso) => { const d = new Date(iso); return (d.getMonth() + 1) + '/' + d.getDate() + ' ' + hhmm(iso); };
async function loadAnalytics(force) {
  if (!force && Date.now() - (S.anAt || 0) < AN_REFRESH_MS) return;
  S.anAt = Date.now();
  const err = $('anErr');
  try { S.an = await getJson('/api/analytics'); } catch (_) {
    // 조용히 넘기면 오래된 숫자가 최신처럼 보인다 — 실패를 알리고, 다음 갱신(10초)에 다시 시도한다
    err.textContent = '분석을 불러오지 못했습니다 · 10초 뒤 다시 시도합니다' + (S.an ? ' · 아래는 이전 값' : '');
    err.hidden = false;
    return;
  }
  err.hidden = true;
  renderAnalytics();
  renderHomeWatch();
  renderHomeMade();
}


function anPanel(id) {
  const el = $(id);
  el.querySelectorAll(':scope > :not(h2)').forEach((n) => n.remove());
  return el;
}
function anRow(parent, cls, html, ids, title) {
  const b = document.createElement('button');
  b.type = 'button'; b.className = cls; b.innerHTML = html;
  b.addEventListener('click', () => openIncidents(title, ids));
  parent.appendChild(b);
  return b;
}
// 칸에 줄이 없는 나머지 설비를 한 줄로: "정지 없음 · PDP-01 · GR-01 …" — 전체 설비가 빠짐없이 보이게
function restLine(parent, label, shownIds) {
  const shown = new Set(shownIds);
  const rest = S.equipment.filter((e) => !shown.has(e.equipment_id)).map((e) => e.code);
  if (!rest.length) return;
  const p = document.createElement('p'); p.className = 'an-rest';
  p.textContent = label + ' · ' + rest.join(' · ');
  parent.appendChild(p);
}
function anEmpty(parent, text) {
  const p = document.createElement('p'); p.className = 'hint'; p.style.margin = '0'; p.textContent = text; parent.appendChild(p);
}

const ymd = (d) => { const x = new Date(d); return x.getFullYear() + '/' + String(x.getMonth() + 1).padStart(2, '0') + '/' + String(x.getDate()).padStart(2, '0'); };
const periodText = (from, to, basis) => ymd(from) + ' - ' + ymd(to) + ' (' + basis + ' 기준)';
const clockText = () => new Date((S.snap && S.snap.simulated_at) || Date.now()).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
const lossKind = (id) => (((S.equipment.find((e) => e.equipment_id === id) || {}).code || '').split('-')[0] || '기타').toUpperCase();
const lossPct = (n, d) => (d ? +(n / d * 100).toFixed(1) : 0) + '%';
// 설비군 = 코드 앞부분(HPU·RT·CV…). 손실이 큰 3군 + 나머지는 '기타'.
function lossGroups(v) {
  const by = {};
  S.equipment.forEach((e) => { const k = lossKind(e.equipment_id); (by[k] = by[k] || {key: k, ids: [], coils: 0}).ids.push(e.equipment_id); });
  v.rows.forEach((r) => { const g = by[lossKind(r.equipment_id)]; if (g) g.coils += r.coils; });
  const all = Object.values(by).sort((p, q) => q.coils - p.coils || q.ids.length - p.ids.length);
  const groups = all.slice(0, 3).map((g) => ({...g, color: 'var(--' + g.key.toLowerCase() + ')'}));
  const rest = all.slice(3);
  if (rest.length) groups.push({key: '기타', ids: rest.flatMap((g) => g.ids), coils: rest.reduce((n, g) => n + g.coils, 0), color: 'var(--tx-3)'});
  return groups;
}
function renderLoss(loss, v) {
  const f1 = (n) => n.toFixed(1) + '%', groups = lossGroups(v), el = document.createElement('div');
  const asof = '오늘 ' + clockText() + ' 기준';
  const redraw = () => { loss.scrollTop = 0; renderAnalytics(); };
  if (!S.lossDetail) {
    el.innerHTML = '<section class="ls-card"><header><h3>생산 현황</h3><span class="per"></span><span class="asof"></span></header>'
      + '<div class="ls-now"><span class="lb">현재 생산</span><span class="val"><b class="mono"></b><small>개</small><span class="plan"></span></span></div>'
      + '<div class="ls-bar" role="img"><i></i></div><div class="ls-sub"><span class="b"></span></div></section>'
      + '<section class="ls-card ls-loss"><header><h3>정지 손실</h3><b class="lostn mono"></b></header>'
      + '<p class="ls-note"></p><div class="ls-stack" role="img"></div><ul class="ls-legend"></ul>'
      + '<button type="button" class="ls-detail">설비별 상세</button></section>';
    const q = (s) => el.querySelector(s);
    const cur = Math.floor((S.prod && S.prod.coils) || 0), curPct = v.planned ? cur / v.planned * 100 : 0;   // 현재 생산 = tickProduction 누적
    q('.asof').textContent = asof;
    q('.per').textContent = periodText(S.an.week_start, S.an.now, '1주');
    q('.ls-now b').textContent = cur.toLocaleString();
    q('.ls-now .plan').textContent = '/ 계획 ' + v.planned.toLocaleString() + '개';
    q('.ls-bar i').style.width = curPct + '%';
    q('.ls-bar').setAttribute('aria-label', '계획 ' + v.planned + '개 중 현재 생산 ' + cur + '개');
    q('.ls-sub .b').textContent = '잔여 ' + Math.max(0, v.planned - cur).toLocaleString() + '개';
    q('.lostn').innerHTML = v.lost.toLocaleString() + '<small>개</small>';
    q('.ls-note').textContent = '설비군별 합계 · 전체 ' + S.equipment.length + '대';
    q('.ls-stack').innerHTML = groups.filter((g) => g.coils).map((g) => '<i style="flex:' + g.coils + ';background:' + g.color + '"></i>').join('');
    q('.ls-stack').setAttribute('aria-label', '손실 ' + v.lost + '개 — ' + groups.map((g) => g.key + ' ' + g.coils + '개').join(', '));
    q('.ls-legend').innerHTML = groups.map((g) => '<li><i style="background:' + g.color + '"></i><b>' + g.key + ' ' + g.ids.length + '대</b><span>'
      + g.coils + '개 · ' + lossPct(g.coils, v.lost) + '</span></li>').join('');
    q('.ls-detail').addEventListener('click', () => { S.lossDetail = true; S.lossGroup = (groups[0] || {}).key; redraw(); });
    loss.appendChild(el);
    return;
  }
  // 설비별 상세 — 이 칸 전체. 탭 = 설비군, 표 = 그 군의 설비(누르면 그 설비의 사건 목록).
  const g = groups.find((x) => x.key === S.lossGroup) || groups[0];
  el.innerHTML = '<div class="ld-head"><button type="button" class="ld-back">' + '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>이전</button>'
    + '<h3>설비별 정지 손실</h3><span class="asof"></span></div>'
    + '<div class="ld-tabs" role="tablist"></div>'
    + '<div class="ld-band"><span class="t"></span><b class="mono"></b><span class="r"></span></div>'
    + '<p class="ld-cmp"></p><div class="ld-table"><div class="ld-th"><span>설비</span><span class="gn"></span><span>손실량</span></div></div>';
  const q = (s) => el.querySelector(s);
  q('.asof').textContent = asof;
  q('.ld-back').addEventListener('click', () => { S.lossDetail = false; redraw(); });
  groups.forEach((x) => {
    const t = document.createElement('button'); t.type = 'button'; t.setAttribute('role', 'tab');
    t.setAttribute('aria-selected', String(x === g)); t.textContent = x.key + ' ' + x.ids.length + '대';
    if (x.key !== '기타') { const dot = document.createElement('i'); dot.className = 'eqchip'; dot.style.background = x.color; t.prepend(dot); }   // 탭 앞 둥근 색(기타 제외)
    t.addEventListener('click', () => { S.lossGroup = x.key; redraw(); });
    q('.ld-tabs').appendChild(t);
  });
  q('.ld-band .t').textContent = g.key + ' 정지 손실';
  q('.ld-band b').innerHTML = g.coils.toLocaleString() + '<small>개</small>';
  q('.ld-band .r').innerHTML = '전체 손실 ' + v.lost.toLocaleString() + '개 중 <strong>' + lossPct(g.coils, v.lost) + '</strong>';
  q('.ld-cmp').textContent = '개별 설비 비교 · ' + g.key + ' 손실 ' + g.coils + '개 = 100%';
  q('.ld-th .gn').textContent = g.key + ' 내 손실 비중';
  loss.appendChild(el);
  const rows = g.ids.map((id) => v.rows.find((r) => r.equipment_id === id) || {equipment_id: id, coils: 0, incidents: []})
    .sort((p, q2) => q2.coils - p.coils || eqCode(p.equipment_id).localeCompare(eqCode(q2.equipment_id)));
  const html = '<span class="eqc mono"></span><span class="pct"><span class="bar"><i></i></span><em></em></span><b class="n mono"></b>';
  rows.forEach((r, i) => {
    const title = eqCode(r.equipment_id) + ' 정지 손실';
    let b;   // 사건이 있으면 누르면 로그(사건 목록)로 — 없으면 눌리지 않는 줄
    if ((r.incidents || []).length) b = anRow(q('.ld-table'), 'ld-row', html, r.incidents, title);
    else { b = document.createElement('div'); b.className = 'ld-row'; b.innerHTML = html; q('.ld-table').appendChild(b); }
    if (r.coils && i === 0) b.classList.add('top');
    b.querySelector('.eqc').textContent = eqCode(r.equipment_id);
    if (g.key === '기타') b.querySelector('.eqc').prepend(eqChip(r.equipment_id));   // 기타 탭은 표에서 설비마다 색
    b.querySelector('.bar i').style.width = (g.coils ? r.coils / g.coils * 100 : 0) + '%';
    b.querySelector('em').textContent = lossPct(r.coils, g.coils);
    b.querySelector('.n').textContent = r.coils + '개';
    if (!r.coils) { const s = document.createElement('small'); s.textContent = '손실 없음'; b.querySelector('.n').appendChild(s); }
  });
}
function renderAnalytics() {
  const a = S.an;
  if (!a || S.screen !== 'dashboard') return;
  const keep = ['anLoss', 'anRepeat', 'anGap'].map((id) => [id, $(id).scrollTop]);   // 다시 그려도 칸 스크롤 유지
  renderAnalyticsPanels(a);
  keep.forEach(([id, top]) => { $(id).scrollTop = top; });
}

function renderAnalyticsPanels(a) {

  // 정지 손실 — 못 만든 코일(라인을 세운 시간 × 표준 생산 속도).
  // 요약: 현재 생산(계획 대비) + 정지 손실(설비군별 막대). '설비별 상세'를 누르면 이 칸 전체가 설비별 표로 바뀐다.
  const loss = anPanel('anLoss'), v = lossView(a.production, a.loss);
  loss.classList.toggle('loss-detail', !!(S.lossDetail && v.planned));
  if (v.planned) renderLoss(loss, v);

  const rep = anPanel('anRepeat');
  const repHead = rep.querySelector('h2');
  repHead.replaceChildren(...[['span', '반복 증상', ''], ['small', periodText(Date.parse(a.now) - 28 * 864e5, a.now, '4주'), 'per'], ['small', '오늘 ' + clockText() + ' 기준', 'asof']]
    .map(([tag, text, cls]) => { const e = document.createElement(tag); e.textContent = text; if (cls) e.className = cls; return e; }));
  a.repeats.forEach((g) => {
    const b = anRow(rep, 'an-row', '<b class="eqc mono"></b><span class="m"></span><span class="v mono"></span>',
      g.incidents, eqCode(g.equipment_id) + ' ' + g.label);
    b.querySelector('.eqc').textContent = eqCode(g.equipment_id);
    b.querySelector('.eqc').prepend(eqChip(g.equipment_id));
    b.querySelector('.m').textContent = g.label;
    b.querySelector('.v').textContent = g.count + '회';
  });
  restLine(rep, '반복 없음', a.repeats.map((g) => g.equipment_id));

  // 지식 공백 — 이 MES DB의 실제 기록(합성 이력 없음). 지식 없음 질의 → 카드 초안 → 검수 대기 → 승인 → 카드로 답.
  const gap = anPanel('anGap'), k = a.knowledge;
  if (!k) return;
  const flow = document.createElement('div'); flow.className = 'an-flow';
  [['지식 없음', k.no_knowledge, ''], ['카드 초안', k.drafts, ''], ['검수 대기', k.pending, ''],
    ['승인', k.approved, k.approved ? 'ok' : ''], ['카드로 답', k.answered, k.answered ? 'ok' : '']].forEach(([t, n, cls]) => {
    const d = document.createElement('div'); d.className = cls;
    d.innerHTML = '<span class="n mono"></span><span class="t"></span>';
    d.querySelector('.n').textContent = n; d.querySelector('.t').textContent = t;
    if (t === '승인' && k.approved_ids.length) {
      const ids = document.createElement('span'); ids.className = 'ids mono'; ids.textContent = k.approved_ids.join(' '); d.appendChild(ids);
    }
    flow.appendChild(d);
  });
  gap.appendChild(flow);
}

$('homeWatch').addEventListener('click', (e) => {
  const b = e.target.closest('.watch-row'), w = b && (S.homeWatchRows || [])[b.dataset.i];
  if (!w) return;
  openIncidents(w.code + ' ' + w.label, w.incidents); S.dlFrom = 'home';
});
function openIncidents(title, ids) {
  S.dlFrom = null;   // 대시보드에서 열면 '이전'은 대시보드로(홈에서 열 때만 호출한 쪽이 'home'으로 바꾼다)
  const want = new Set(ids);
  const pane = $('dlPane'); pane.innerHTML = '';
  $('dlTitle').textContent = title;
  S.an.incidents.filter((i) => want.has(i.incident_id)).forEach((i) => {
    const d = document.createElement('div'); d.className = 'card inc';
    d.innerHTML = '<div class="top"><span class="mono"></span><b class="mono"></b><span class="lb"></span><span class="pill st"></span></div>'
      + '<div class="nums mono"></div><p class="body"></p><div class="src mono"></div>';
    const [word, cls] = AN_OUTCOME[i.outcome] || ['', 'unknown'];
    d.querySelector('.top span').textContent = mdhm(i.alarm_at);
    d.querySelector('.top b').textContent = eqCode(i.equipment_id);
    d.querySelector('.top b').prepend(eqChip(i.equipment_id));
    d.querySelector('.lb').textContent = i.label;
    const st = d.querySelector('.st'); st.textContent = word; st.className = 'pill st ' + cls;
    d.querySelector('.nums').textContent = '정지 ' + Math.round(i.down_min) + '분'
      + (i.affected.length ? ' · 연쇄 정지 ' + i.affected.length + '대' : '');
    d.querySelector('.body').textContent = [i.action || '조치 기록 없음', i.cause ? '원인 ' + i.cause : '',
      AN_RESULT[i.result] || ''].filter(Boolean).join(' · ');
    const card = i.card_id && S.cards.find((c) => c.card_id === i.card_id);
    d.querySelector('.src').textContent = [i.handover_id, i.card_id ? i.card_id + (card ? ' ' + card.title : '') : '',
      i.recurred_after_days != null ? i.recurred_after_days + '일 뒤 재발' : ''].filter(Boolean).join(' · ');
    pane.appendChild(d);
  });
  show('dashList');
}
on('dlBack', () => {   // 홈 '지켜볼 설비'에서 왔으면 홈으로
  const to = S.dlFrom || 'dashboard'; S.dlFrom = null;
  show(to); if (to === 'dashboard') renderAnalytics();
});

// 현재 생산 — MES 실행(run_id)이 시작된 뒤 라인이 '운전 중'이던 모의 시간 × 시간당 생산 코일 수. 실행이 바뀌면(MES 재시작) 0으로 초기화.
// ponytail: PDA가 켜져 있는 동안만 센다(10분 넘게 끊긴 구간은 세지 않음). 서버 집계로 옮기려면 analytics.py에 가동 시간 합을 추가.
const PROD_KEY = 'shiftlink.production';
function tickProduction(snap) {
  const rate = S.an && S.an.production && S.an.production.coils_per_hour, t = Date.parse(snap.simulated_at);
  let p = S.prod;
  if (!p) { try { p = JSON.parse(localStorage.getItem(PROD_KEY) || 'null'); } catch (_) { p = null; } }
  if (!p || p.run !== snap.run_id || !(t > 0)) p = { run: snap.run_id, last: t, mode: snap.line_mode, coils: 0 };
  else {
    const dt = (t - p.last) / 3600000;   // 시간
    if (rate && p.mode === 'running' && dt > 0 && dt <= 1 / 6) p.coils += dt * rate;
    p.last = t; p.mode = snap.line_mode;
  }
  S.prod = p;
  try { localStorage.setItem(PROD_KEY, JSON.stringify(p)); } catch (_) { /* 저장 실패해도 화면은 계속 */ }
}
async function watchMes() {
  if (S.equipment.length) {
    try {
      const snap = await getJson('/api/state');
      renderAlert(faultsFrom(snap));
      S.snap=snap;S.snapshot=snap;tickProduction(snap);renderDash();if(S.screen==='home')renderHome();
      if (S.eq) await loadMesObservations(snap);   // 화면의 고정 값과 별도로 최신 MES 상태를 감시한다
    } catch (err) { S.snapshot=null;if(S.screen==='home')renderHome();if (S.eq) clearMesObservations(); console.warn('MES 감시 실패', err); }
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
