(() => {
  const labels = { running: "가동", paused: "일시정지", stopped: "정지", waiting: "대기", fault: "이상", recovering: "복구 관찰", warning: "주의", critical: "고장", normal: "정상", recovery: "복구 중", downstream_block: "하류 정체", upstream_drive_fault: "상류 구동 이상", hydraulic_supply_low: "유압 공급 저하", self_fault: "자체 이상", material_shortage: "소재 부족", planned_stop: "계획 정지" };
  const label = (value) => labels[value] || value || "—";
  labels.quality_hold = "제품 검사·보류";
  const relationLabels = { material_flow: "소재 이송", utility_supply: "유틸리티 공급", hydraulic_supply: "유압 공급", pneumatic_supply: "공압 공급", power_supply: "전력 공급", mechanical_drive: "기계 구동", drive: "구동", interlock: "인터록", common_mode: "공통 영향", co_occurrence: "동시 발생 관계" };
  const escape = (value) => String(value ?? "—").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
  const stateClass = (item) => item.fault_level === "warning" ? "warning" : item.fault_level && item.fault_level !== "normal" ? "fault" : item.operating_state === "waiting" ? "waiting" : item.operating_state === "stopped" ? "stopped" : "normal";
  const statusText = (item) => [label(item.operating_state), label(item.fault_level), item.wait_reason && label(item.wait_reason)].filter(Boolean).join(" · ");
  const clock = (value) => value ? new Date(value).toLocaleString("ko-KR", { hour12: false }) : "—";
  const eventLabels = {started:"운전 시작",paused:"일시정지",scenario_selected:"시나리오 선택",alarm_raised:"알람 발생",alarm_cleared:"알람 해제",recovery_started:"복구 시작",recovery_action_completed:"조치 기록",recovered:"복구 완료",coil_entered:"코일 투입",coil_exited:"코일 배출",coil_held:"코일 보류",coil_released:"코일 보류 해제"};
  function eventText(event, config) {
    const equipment = config?.equipment?.find(e=>e.equipment_id===event.equipment_id);
    return [eventLabels[event.event_type] || event.event_type, equipment?.code || event.equipment_id].filter(Boolean).join(" · ");
  }
  function metricWindow(snapshot, snapshots) {
    const metrics = operationMetrics(snapshots);
    return metrics.samples ? `최근 모의 운전 ${metrics.windowMinutes}분 · 측정 ${metrics.samples}회` : `데이터 부족 (${snapshots.length}/${METRIC_MIN_SNAPSHOTS}회)${snapshot.line_mode === "paused" ? " · 운전 재개 후 집계" : " · 측정 기록이 쌓이면 집계"}`;
  }
  const processRoles = {
    rt: ["롤러 이송대", "여러 롤러가 코일을 받쳐 다음 장비로 옮깁니다."],
    cv: ["컨베이어", "벨트 위의 코일을 출측으로 운반합니다."],
    gr: ["감속기·모터", "모터의 회전을 전달해 연결된 이송 장비를 움직입니다."],
    hpu: ["유압 공급장치", "기름에 압력을 만들어 클램프와 승강 장치를 움직이게 합니다."],
    pdp: ["배전반", "연결된 장비에 전기를 공급합니다."],
    cau: ["공압 공급장치", "압축 공기를 연결된 장비에 공급합니다."]
  };
  function equipmentKind(eq = {}) {
    const kind = String(eq.profile_id || eq.code?.split("-")[0] || "").toLowerCase();
    return Object.hasOwn(processRoles, kind) ? kind : "generic";
  }
  const roleFor = (eq) => processRoles[equipmentKind(eq)] || ["설비", "역할은 설비 구성과 연결 정보를 확인하세요."];
  function machineMoving(snapshot, item, playing) {
    return playing && !["paused", "stopped", "recovering"].includes(snapshot.line_mode) && item?.operating_state === "running" && ["normal", "warning"].includes(item.fault_level);
  }
  function processMessage(snapshot, config) {
    if (snapshot.line_mode === "quality_hold") return "설비 고장은 해소되었지만 영향 코일의 검사·보류 해제가 남아 있습니다. 보류 코일은 이동하거나 배출되지 않습니다.";
    const names = (items) => items.map(e => config?.equipment?.find(c => c.equipment_id === e.equipment_id)?.code || e.equipment_id).join(", ");
    const faults = (snapshot.equipment || []).filter(e => stateClass(e) === "fault");
    const waiting = (snapshot.equipment || []).filter(e => e.operating_state === "waiting");
    if (faults.length) return `${names(faults)}에 자체 이상이 있습니다. ${waiting.length ? `${names(waiting)}은 대기 중입니다. 대기만으로 해당 장비의 고장을 뜻하지는 않습니다.` : "다른 장비의 운전 상태를 함께 확인하세요."}`;
    if (snapshot.line_mode !== "running") return "운전이 멈춰 있습니다. 코일과 장비의 움직임도 멈춥니다.";
    if (waiting.length) return `${names(waiting)}이 기다리고 있습니다. 장비를 선택하면 대기 이유를 확인할 수 있습니다.`;
    return "코일은 아래 번호 순서로 이동합니다. 구동·공급 장비는 이송을 돕고, 코일이 통과하는 경로와는 구분됩니다.";
  }
  // 최근 스냅샷 창으로 계산한 운영 지표. 표본이 적으면 계산하지 않는다(화면은 "집계 중").
  const METRIC_MIN_SNAPSHOTS = 10;
  function operationMetrics(snapshots) {
    const out = {}, n = snapshots.length;
    if (n < METRIC_MIN_SNAPSHOTS) return out;
    const at = (s) => Date.parse(s.simulated_at) / 1000;
    const slot = (id) => (out[id] ||= { up: 0, coils: new Map() });
    snapshots.forEach((s, i) => {
      for (const e of s.equipment || []) slot(e.equipment_id).up += e.operating_state === "running" && e.fault_level === "normal" ? 1 : 0;
      const next = snapshots[i + 1], there = new Map((next?.coils || []).map((c) => [c.coil_id, c.equipment_id]));
      for (const c of s.coils || []) {
        const coils = slot(c.equipment_id).coils;
        // 창 첫 스냅샷에 이미 있던 코일은 들어온 시각을 모른다 — 처리량엔 넣고 머문 시간에선 뺀다
        if (!coils.has(c.coil_id)) coils.set(c.coil_id, { from: i === 0 ? null : at(s), to: null });
        if (next && there.get(c.coil_id) !== c.equipment_id) coils.get(c.coil_id).to = at(next);   // 다음 설비로 갔거나 배출됨
      }
    });
    for (const m of Object.values(out)) {
      const left = [...m.coils.values()].filter((r) => r.to != null), stays = left.filter((r) => r.from != null).map((r) => r.to - r.from);
      m.utilization = Math.round(m.up / n * 100);
      m.throughput = left.length;
      m.cycle = stays.length ? Math.round(stays.reduce((a, b) => a + b, 0) / stays.length * 10) / 10 : null;
    }
    out.windowMinutes = Math.round((at(snapshots.at(-1)) - at(snapshots[0])) / 6) / 10;
    out.samples = n;
    return out;
  }
  function operationRows(snapshot, config, snapshots = []) {
    const alarms = snapshot.active_alarms || [], coils = snapshot.coils || [], measurements = snapshot.measurements || [];
    const metrics = operationMetrics(snapshots), route = config?.route || [];
    return (snapshot.equipment || []).map((state) => {
      const equipment = config?.equipment?.find(item => item.equipment_id === state.equipment_id) || {};
      const cycle = measurements.find(item => item.equipment_id === state.equipment_id && /cycle.*time|cycle_time/i.test(item.signal));
      const queue = coils.filter(coil => coil.equipment_id === state.equipment_id).length;
      const alerts = alarms.filter(alarm => alarm.equipment_id === state.equipment_id).length;
      const active = state.operating_state === "running" && state.fault_level === "normal";
      const m = metrics[state.equipment_id], onRoute = route.includes(state.equipment_id);   // 코일이 지나가는 설비만 처리량이 있다
      const cycleTime = onRoute && m?.cycle != null ? `${m.cycle} s` : cycle ? `${cycle.value} ${cycle.unit}` : null;
      const alarm = alarms.find(a => a.equipment_id === state.equipment_id);
      return { equipment_id: state.equipment_id, name: equipment.code || equipment.name || state.equipment_id, status: state.operating_state, faultLevel: state.fault_level, onRoute, throughput: onRoute && m ? m.throughput : null, utilization: m ? m.utilization : null, queue, cycleTime, alerts, alarmLabel: alarm ? (alarm.label || alarm.code) : "", changed: !active || alerts > 0 };
    });
  }
  function createHistory() { return { runId: null, cursor: -1, events: [], snapshots: [], completed: 0 }; }
  function createConfigCache() { return { config: null, configId: null }; }
  function configsCompatible(old, new_) { if (!old || !new_) return false; return old.config_id === new_.config_id; }
  function getTraceUnit(config, equipmentId, signal) { if (!config) return ""; const eq = config.equipment?.find(e => e.equipment_id === equipmentId); return eq?.signals?.find(s => s.signal === signal)?.unit || ""; }
  function shouldBreakTrace(prevMeasurement, measurement, config) { if (!prevMeasurement || !measurement) return true; const oldUnit = getTraceUnit(config, prevMeasurement.equipment_id, prevMeasurement.signal); const newUnit = getTraceUnit(config, measurement.equipment_id, measurement.signal); return oldUnit !== newUnit; }
  function acceptSnapshot(history, snapshot) {
    if (history.runId !== snapshot.run_id) Object.assign(history, createHistory(), { runId: snapshot.run_id });
    const previous = history.snapshots.at(-1);
    if (previous?.sequence === snapshot.sequence) history.snapshots[history.snapshots.length - 1] = snapshot;
    else history.snapshots.push(snapshot);
    history.snapshots = history.snapshots.slice(-180);
  }
  function acceptEvents(history, payload) {
    if (payload.run_id !== history.runId) return false;
    const key = (event) => JSON.stringify([event.run_id, event.sequence, event.event_type, event.equipment_id, event.observation, event.occurred_at]);
    const seen = new Set(history.events.map(key));
    for (const event of payload.events || []) {
      if (event.run_id !== history.runId) continue;
      history.cursor = Math.max(history.cursor, Number(event.sequence));
      if (!seen.has(key(event))) { history.events.push(event); seen.add(key(event)); if (event.event_type === "coil_exited") history.completed++; }
    }
    history.events = history.events.slice(-100);
    return true;
  }
  const connectionState = (lastReceived, now, mode) => now - lastReceived > 10000 ? "데이터 수신 지연" : mode === "paused" ? "연결됨 · 일시정지" : "연결됨";
  function recoveryView(snapshot, interactive) {
    const plan = snapshot.recovery;
    if (!plan) return '<p class="empty-state">시연 제어에서 시나리오를 선택하면 필요한 조치와 복귀 조건을 볼 수 있습니다.</p>';
    const done = plan.stage === "completed", next = plan.actions.findIndex(a => !a.completed);
    const steps = [{title: "이상 발생", done: true}, ...plan.actions.map((a, i) => ({title:a.title, done:a.completed, unrecorded:!a.completed && ["stabilizing","completed"].includes(plan.stage), current:plan.stage === "actions" && i === next})),
      {title: "안정화 관찰", done, current:plan.stage === "stabilizing"}, {title: "정상 복귀", done}];
    const flow = steps.map((s, i) => `<li class="${s.done ? "done" : ""} ${s.current ? "current" : ""}" ${s.current ? 'aria-current="step"' : ''}><span>${s.done ? "✓" : i + 1}</span><b>${escape(s.title)}</b><small>${s.current ? "현재 단계" : s.done ? "완료" : s.unrecorded ? "조치 기록 없음" : "대기"}</small></li>`).join("");
    const action = plan.stage === "actions" ? plan.actions[next] : null;
    const status = done ? "정상 복귀 완료" : plan.stage === "ready" ? "필수 조치 완료 · 모의 복구 시작을 눌러 안정화 관찰을 시작하세요." : plan.stage === "stabilizing" ? `안정화 관찰 중 · 모의 관찰 ${plan.remaining_ticks}회 남음${snapshot.line_mode === "paused" ? " · 재개 버튼을 누르세요." : ""}` : plan.required === false ? "안내된 조치를 차례로 기록하거나 바로 복귀를 진행할 수 있습니다." : "다음 조치를 완료해야 복귀할 수 있습니다.";
    const held = (snapshot.coils || []).filter(c => c.quality_status === "hold");
    const source = /^https:\/\//.test(plan.source_url || "") ? `<a href="${escape(plan.source_url)}" target="_blank" rel="noopener noreferrer">근거 매뉴얼 ↗</a>` : "";
    return `<div class="recovery-heading"><h3>${escape(plan.title)}</h3>${source}</div><ol class="recovery-flow" aria-label="정상 복귀 단계">${flow}</ol><p class="recovery-status">${escape(status)}</p>${action ? `<div class="next-action"><div><b>${escape(action.title)}</b><p>${escape(action.detail)}</p></div>${interactive ? `<button type="button" class="primary-button" data-action="${escape(action.action_id)}">조치 완료</button>` : '<span class="hint">기록 조회 전용</span>'}</div>` : ""}${interactive && plan.stage === "ready" ? '<button type="button" class="primary-button" data-command="recover">모의 복구 시작 · 안정화 관찰</button>' : ""}${interactive && plan.stage === "actions" && plan.required === false ? '<p class="hint">이 시나리오의 조치는 원인별 절차가 아닌 일반 안내입니다.</p><button type="button" data-command="recover">조치 기록 없이 모의 복구 시작</button>' : ""}${interactive && snapshot.line_mode === "paused" ? '<button type="button" data-command="resume">모의 운전 재개</button>' : ""}${held.length ? `<p class="held-coils">보류 코일 ${held.length}개 · ${held.map(c => escape(c.coil_id)).join(" · ")}</p>` : ""}`;
  }
  function componentView(snapshot, equipmentId) {
    const parts = (snapshot.components || []).filter(c => c.equipment_id === equipmentId);
    if (!parts.length) return '<p class="hint">부품 상태 기록 없음 · 이 설비 또는 과거 실행에는 모의 내구도 정보가 없습니다.</p>';
    return `<div class="component-list">${parts.map(c => {
      const value = Math.max(0, Math.min(100, Number(c.health_percent))), state = value < 40 ? "점검 필요" : value < 70 ? "주의" : "양호";
      return `<article class="component-card ${value < 40 ? "degraded" : ""}"><div><b>${escape(c.name)}</b><strong>${value.toFixed(1)}% · ${state}</strong></div><meter min="0" max="100" low="40" high="70" optimum="100" value="${value}" aria-label="${escape(c.name)} 모의 건전도">${value.toFixed(1)}%</meter><small>누적 운전 ${(c.operating_seconds / 3600).toFixed(3)} h · 정비 ${Number(c.maintenance_count)}회${c.last_maintenance_at ? ` · 최근 ${escape(clock(c.last_maintenance_at))}` : ""}</small></article>`;
    }).join("")}</div>`;
  }
  if (typeof module !== "undefined") module.exports = { createHistory, acceptSnapshot, acceptEvents, connectionState, stateClass, equipmentKind, machineMoving, processMessage, operationRows, operationMetrics, metricWindow, eventText, recoveryView, componentView };
  if (typeof document === "undefined") return;
  const operator = globalThis.MesOperator;
  const $ = (selector) => document.querySelector(selector);
  const setText = (selector, value) => { const el = $(selector); if (el) el.textContent = value; };
  let selectedId = null, lastSnapshot = null, mode = "live", lastReceived = 0, lastAdvance = 0;
  let selectedRelation = "", selectedPartId = null, incidentSignature = "", stale = true;
  let history = createHistory(), requestEpoch = 0, loading = false, controlPending = false, applyPending = false;
  let liveConfig = createConfigCache(), replayConfig = createConfigCache();
  let replay = { snapshots: [], events: [], index: 0, playing: false, configId: null, configPreserved: true };
  function setConnection(message, kind = "") { setText("#connection-status", message); $("#connection-status").className = `status-label ${kind}`; setText("#diagram-connection",message); $("#diagram-connection").className = kind; }
  async function request(url, options = {}) {
    const response = await fetch(url, { ...options, signal: AbortSignal.timeout(7000) });
    if (!response.ok) { const error = await response.json().catch(() => ({})); throw new Error(error.error || `요청 실패 (${response.status})`); }
    const data = await response.json();
    if (!data.is_synthetic) throw new Error("합성 데이터 표기가 없는 응답");
    return data;
  }
  const info = (id, config) => config?.equipment?.find((item) => item.equipment_id === id) || {};
  const name = (id, config) => info(id, config).name || info(id, config).code || id;
  function setView(selector, html) {
    const el = $(selector); if (el.dataset.html === html) return;
    const active = document.activeElement, focused = active && el.contains(active);
    const keys = focused ? ["data-action", "data-command", "data-part", "data-equipment", "data-relation"].filter(k=>active.hasAttribute(k)).map(k=>[k,active.getAttribute(k)]) : [];
    const summaryIndex = focused ? [...el.querySelectorAll("summary")].indexOf(active) : -1;
    const open = [...el.querySelectorAll("details")].map(d=>d.open);
    el.innerHTML = html; el.dataset.html = html;
    el.querySelectorAll("details").forEach((d,i)=>{ if (open[i]!==undefined) d.open=open[i]; });
    if (summaryIndex >= 0) el.querySelectorAll("summary")[summaryIndex]?.focus({preventScroll:true});
    if (focused && keys.length) {
      const target = [...el.querySelectorAll('button,[role="button"]')].find(n=>keys.every(([k,v])=>n.getAttribute(k)===v) && n.hasAttribute("data-relation")===active.hasAttribute("data-relation")) || el.querySelector('[data-action],[data-command="recover"],button');
      (target || $("#equipment-detail"))?.focus({preventScroll:true});
    }
  }
  const currentConfig = () => mode === "live" ? liveConfig.config : replayConfig.config;
  function setDiagramMode(enabled, focus = true) {
    document.body.classList.toggle("diagram-only", enabled);
    $("#diagram-toolbar").hidden = !enabled;
    showWorkspace("flow");
    if (globalThis.location) {
      const url = new URL(globalThis.location.href);
      if (enabled) url.searchParams.delete("view"); else url.searchParams.set("view", "full");  // 기본은 관계도 화면
      globalThis.history.replaceState(null, "", url);
    }
    if (focus) $(enabled ? "#diagram-back" : "#diagram-open").focus();
  }
  function showWorkspace(key, focus = false) {
    const target = document.querySelector(`#tab-${key}`);
    if (!target?.dataset?.workspace) return;
    // 관계도 전용 모드는 설비 흐름만 보여 준다. 상세·이력을 열면 전체 화면으로 나간다(그대로 두면 빈 화면).
    if (key !== "flow" && document.body?.classList.contains("diagram-only")) setDiagramMode(false, false);
    document.querySelectorAll('[role="tab"][data-workspace]').forEach(tab => {
      const selected = tab.dataset.workspace === key;
      tab.setAttribute("aria-selected", String(selected)); tab.tabIndex = selected ? 0 : -1;
      document.querySelector(`#${tab.getAttribute("aria-controls")}`).hidden = !selected;
    });
    if (focus) target.focus();
  }
  function workspaceKeydown(event) {
    const tabs = [...document.querySelectorAll('[role="tab"][data-workspace]')];
    const index = tabs.indexOf(event.target);
    if (index < 0 || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    showWorkspace(tabs[next].dataset.workspace, true);
  }
  function selectEquipment(id, relation="", move=false) {
    if (!lastSnapshot?.equipment?.some(e=>e.equipment_id===id)) return;
    if (id===selectedId && !relation && !move) { clearSelection(); return; }
    selectedId=id; selectedPartId=null; selectedRelation=relation; renderSnapshot(lastSnapshot,currentConfig());
    if (move) { showWorkspace("detail"); $("#equipment-detail").focus(); $("#equipment-detail").scrollIntoView({block:"start"}); }
    setText("#operator-announcement", `${name(id,currentConfig())} 선택. ${move ? "설비 상세에서 측정 정보와 조치를 확인하세요." : "상세 보기 버튼을 누르면 측정 정보와 조치로 이동합니다."}`);
  }
  function clearSelection() {
    selectedId=null; selectedPartId=null; selectedRelation="";
    renderSnapshot(lastSnapshot,currentConfig());
    setText("#operator-announcement","선택 해제. 기본 소재 흐름만 표시합니다.");
  }
  function renderEquipment(snapshot, config) {
    const model=operator.buildOperatorModel(snapshot,config,selectedId,selectedPartId);
    const relation=model.links.find(l=>operator.relationKey(l)===selectedRelation);
    $("#selected-connection").classList.toggle("has-relation", Boolean(relation));
    setText("#selected-connection", relation ? `${relation.from.code || relation.from_id} ${relation.directionSymbol} ${relation.to.code || relation.to_id} · ${relation.label} · ${relation.affected ? "영향으로 대기 중인 설비" : "구성상 연결 · 원인 확정 아님"}` : selectedId ? `${name(selectedId,config)} 직접 관계와 기본 소재 흐름을 표시합니다. 강조 필터는 선을 숨기지 않습니다.` : "기본 소재 흐름 · 설비를 선택하면 직접 연결된 관계를 추가합니다.");
    setText("#process-story",processMessage(snapshot,config));
    setView("#line-map",operator.flowView(model,$("#experience-mode").value,$("#relation-filter").value,selectedRelation));
    setView("#relation-legend",operator.legendView($("#experience-mode").value));
    setView("#diagram-legend-content",operator.legendView("expert"));
    const playing=$("#animate-machines").checked && (mode==="live" ? !stale : replay.playing);
    $("#line-map").querySelectorAll(".flow-node").forEach(n=>n.classList.toggle("is-moving",machineMoving(snapshot,model.lookup(n.dataset.equipment),playing)));
    $("#line-map").querySelectorAll(".flow-coil").forEach(node=>{
      const coil=(snapshot.coils || []).find(c=>c.coil_id===node.dataset.coil);
      if (!coil) return;
      const moving=coil.quality_status!=="hold" && machineMoving(snapshot,model.lookup(coil.equipment_id),playing);
      node.style.transition=moving?"cx 1s linear":"none";
      node.style.cx=String(-60+Math.max(0,Math.min(1,Number(coil.position)||0))*120)+"px";
      node.querySelector("title").textContent=`${coil.coil_id} · 위치 ${Math.round(Number(coil.position)*100)}%${coil.quality_status==="hold"?" · 제품 보류":""}`;
    });
    setView("#incident-summary",operator.incidentView(model));
    setView("#part-locator",model.selected ? operator.partView(model) : "");
    $("#part-evidence-note").hidden = !model.selectedPart;
    setView("#selection-evidence",model.selected ? operator.evidenceView(model,selectedRelation) : "");
    setView("#utility-links",model.links.filter(l=>l.relation_type!=="material_flow" && [l.from_id,l.to_id].includes(selectedId)).map(l=>`<p><button type="button" data-equipment="${escape(l.from_id)}">${escape(l.from.code || l.from_id)}</button> ${l.directionSymbol} <button type="button" data-equipment="${escape(l.to_id)}">${escape(l.to.code || l.to_id)}</button> · ${escape(l.label)} <button type="button" data-equipment="${escape(selectedId)}" data-relation="${escape(operator.relationKey(l))}" aria-label="${escape(l.from.code || l.from_id)} ${l.directionSymbol} ${escape(l.to.code || l.to_id)} · ${escape(l.label)} 연결 선택">연결 선택</button></p>`).join("") || "설비를 선택하면 직접 관계를 표시합니다.");
    const signature=JSON.stringify([snapshot.run_id,model.faults.map(n=>n.equipment_id),model.held.map(c=>c.coil_id),snapshot.recovery?.stage]);
    if (signature!==incidentSignature) { incidentSignature=signature; setText("#operator-announcement",`상태 변경. 자체 이상·주의 ${model.faults.length}대, 보류 코일 ${model.held.length}개. 우선 확인 항목에서 상세를 선택하세요.`); }
  }
  function renderDetail(snapshot, config) {
    const equipment = snapshot.equipment?.find((item) => item.equipment_id === selectedId);
    const measurements = (snapshot.measurements || []).filter((item) => item.equipment_id === selectedId);
    const configEq = config?.equipment?.find((e) => e.equipment_id === selectedId);
    if (!equipment) {
      setView("#equipment-detail",`<h2>설비 상세</h2><p>확인할 설비를 선택하세요.</p><div class="equipment-choices">${(config?.equipment || []).map(e=>`<button type="button" data-equipment="${escape(e.equipment_id)}">${escape(e.code)} · ${escape(roleFor(e)[0])}</button>`).join("")}</div>`);
      $("#signal-select").innerHTML=""; $("#signal-select").dataset.signals="";
      $("#sensor-trends").innerHTML=""; setText("#trend-description","설비를 선택하면 추이를 표시합니다.");
      return;
    }
    const configInfo = config ? `<p class="config-ref">구성 <small>${config.version_label || config.config_id?.slice(0, 8)}</small></p>` : "";
    const assetInfo = configEq?.asset_id ? `<p>자산 ID: ${escape(configEq.asset_id)}</p>` : "";
    const profileInfo = configEq?.profile_id ? `<p>프로필: ${escape(configEq.profile_id)}</p>` : "";
    setView("#equipment-detail", `<p class="eyebrow">SELECTED EQUIPMENT</p><h2>${escape(configEq?.code || selectedId)} · ${escape(roleFor(configEq)[0])}</h2><p class="selected-state">${escape(statusText(equipment))}</p><details><summary>설비 식별 정보</summary><p>${escape(name(selectedId, config))} · ${escape(selectedId)}</p>${assetInfo}${profileInfo}${configInfo}</details>`);
    const select = $("#signal-select"), signature = (configEq?.signals || []).map((s) => s.signal).join("|");
    if (select.dataset.signals !== signature) {
      select.innerHTML = (configEq?.signals || []).map((s) => `<option value="${escape(s.signal)}">${escape(s.name || s.signal)}${operator.unitText(s.unit) ? ` (${escape(operator.unitText(s.unit))})` : ""}</option>`).join("");
      select.dataset.signals = signature;
    }
    renderTrend(config);
  }
  function renderTrend(config) {
    const signal = $("#signal-select").value;
    const snapshots = mode === "live" ? history.snapshots : replay.snapshots.slice(Math.max(0, replay.index - 179), replay.index + 1);
    const values = [];
    for (const s of snapshots) {
      const m = s.measurements?.find((m) => m.equipment_id === selectedId && m.signal === signal);
      if (Number.isFinite(m?.value)) {
        if (values.length && shouldBreakTrace(values[values.length - 1].measurement, m, config)) values.push({ time: s.simulated_at, measurement: null });
        values.push({ time: s.simulated_at, measurement: m });
      }
    }
    if (!values.length) { $("#sensor-trends").textContent = "추이 데이터 없음"; setText("#trend-description", "설비와 신호를 선택하세요."); return; }
    const numbers = values.filter((p) => p.measurement).map((p) => p.measurement.value), min = Math.min(...numbers), max = Math.max(...numbers), spread = max - min || 1;
    const coordinates = values.map((v, i) => v.measurement ? `${35 + i / Math.max(1, values.length - 1) * 370},${120 - (v.measurement.value - min) / spread * 90}` : null).filter(Boolean).join(" ");
    const unit = operator.unitText(values.find((p) => p.measurement)?.measurement?.unit || "");
    const signalName = $("#signal-select").selectedOptions[0]?.textContent || signal;
    const description = `${signalName} · ${numbers.length}개 관측 · 최소 ${min} / 최대 ${max} ${unit} · ${clock(values[0].time)} ~ ${clock(values.at(-1).time)}`;
    $("#sensor-trends").innerHTML = coordinates ? `<svg viewBox="0 0 420 150" role="img" aria-label="${escape(description)}"><title>${escape(description)}</title><path d="M35 15 V125 H410" fill="none" stroke="currentColor" opacity=".4"/><polyline points="${coordinates}" fill="none" stroke="#5b95c8" stroke-width="3"/><text x="3" y="20" fill="currentColor" font-size="10">${max}</text><text x="3" y="123" fill="currentColor" font-size="10">${min}</text></svg>` : `<p class="empty-state">추이 데이터 없음</p>`;
    setText("#trend-description", description);
  }
  // 현황판: 코일 이송 라인 설비마다 상태 막대 · 가동률 게이지 · 처리량·사이클·대기 · 큰 상태 글씨
  function gauge(pct) {
    const r = 34, c = 2 * Math.PI * r, on = pct == null ? 0 : Math.max(0, Math.min(100, pct)) / 100 * c;
    return `<svg class="board-gauge" viewBox="0 0 84 84" aria-hidden="true"><circle class="gauge-track" cx="42" cy="42" r="${r}"/><circle class="gauge-value" cx="42" cy="42" r="${r}" stroke-dasharray="${on} ${c}" transform="rotate(-90 42 42)"/><text x="42" y="38" class="gauge-label">가동률</text><text x="42" y="56" class="gauge-number">${pct == null ? "자료 부족" : `${pct}%`}</text></svg>`;
  }
  function renderLineBoard(snapshot, config, snapshots) {
    const rows = operationRows(snapshot, config, snapshots).filter(r => r.onRoute);
    const order = config?.route || [];
    rows.sort((a, b) => order.indexOf(a.equipment_id) - order.indexOf(b.equipment_id));
    setView("#line-board", rows.map(r => {
      const eq = config?.equipment?.find(e => e.equipment_id === r.equipment_id);
      const kind = r.faultLevel !== "normal" ? "fault" : r.status === "running" ? "run" : r.status === "waiting" ? "wait" : "stop";
      const state = { fault: label(r.faultLevel) === "고장" ? "정지 · 고장" : `이상 · ${label(r.faultLevel)}`, run: "가동중", wait: "대기", stop: label(r.status) }[kind];
      return `<button type="button" class="board-card ${kind}" data-equipment="${escape(r.equipment_id)}"><span class="board-head"><b>${escape(r.name)}</b><small>${escape(roleFor(eq)[0])}</small></span><i class="board-bar" aria-hidden="true"></i><span class="board-body">${gauge(r.utilization)}<dl><dt>처리량</dt><dd>${r.throughput ?? "—"}<small> 코일</small></dd><dt>평균 이송 시간</dt><dd>${r.cycleTime ? escape(r.cycleTime) : "—"}</dd><dt>설비 내 코일</dt><dd>${r.queue}</dd></dl></span><span class="board-state">${escape(state)} · 상세 보기 →</span></button>`;
    }).join(""));
  }
  // 상태 색만 사용해 주의·이상과 설비 종류 색을 혼동하지 않게 한다.
  function renderUtilBars(snapshot, config, snapshots) {
    const rows = operationRows(snapshot, config, snapshots);
    setView("#util-bars", rows.map(r => {
      const pct = r.utilization, color = r.faultLevel === "warning" ? "#efc78b" : r.faultLevel !== "normal" ? "#ff8f86" : "#aebcc7";
      return `<button type="button" data-equipment="${escape(r.equipment_id)}" class="util-row ${r.faultLevel !== "normal" ? "fault" : ""}" aria-label="${escape(r.name)} · ${escape(label(r.status))} · 가동률 ${pct == null ? "데이터 부족" : `${pct}%`} · 상세 보기"><span class="util-name"><i style="background:${color}"></i>${escape(r.name)}</span><span class="util-track"><span class="util-fill" style="width:${pct ?? 0}%;background:${color}"></span></span><b class="util-pct">${pct == null ? "—" : `${pct}%`}</b></button>`;
    }).join(""));
    setText("#util-window", metricWindow(snapshot, snapshots));
  }
  function renderOperations(snapshot, config, snapshots) {
    const rows = operationRows(snapshot, config, snapshots).filter(row=>$("#operations-filter").value !== "attention" || row.changed);
    setText("#operations-window", metricWindow(snapshot, snapshots));
    const pending = '<span class="muted">데이터 부족</span>', support = '<span class="muted" title="코일이 지나가지 않는 설비라 집계하지 않습니다">해당 없음</span>';
    setView("#operations-body", rows.map(row => `<tr class="${row.changed ? stateClass({operating_state:row.status, fault_level:row.faultLevel !== "normal" ? row.faultLevel : row.alerts ? "warning" : "normal"}) : ""}"><th scope="row"><button type="button" data-equipment="${escape(row.equipment_id)}">${escape(row.name)}</button></th><td>${escape(label(row.status))}${row.faultLevel !== "normal" ? ` · ${escape(label(row.faultLevel))}` : ""}</td><td>${!row.onRoute ? support : row.throughput ?? pending}</td><td>${row.utilization == null ? pending : `${row.utilization}%`}</td><td>${row.queue}</td><td>${!row.onRoute ? support : row.cycleTime ? escape(row.cycleTime) : pending}</td><td>${row.alerts ? `<button type="button" data-equipment="${escape(row.equipment_id)}">⚠ ${escape(row.alarmLabel)}</button>` : "없음"}</td></tr>`).join("") || '<tr><td colspan="7">표시할 설비 없음</td></tr>');
  }
  // 시나리오 100여 개를 원인 설비별로 나눠 두 단계(설비 → 시나리오)로 고른다. 설비가 정해지지 않은 것은 "주요 고장".
  let pickedScenarioGroup = null;   // 작업자가 설비 목록에서 고른 묶음. 시나리오를 적용하면 비운다
  function scenarioGroups(config) {
    const groups = new Map();
    for (const s of (config?.scenarios || []).filter(s => s.scenario_id !== "normal")) {
      const key = s.cause_equipment_id ? name(s.cause_equipment_id, config) : "주요 고장";
      const title = s.title || ({drive_fault: "구동부 진동 이상", hydraulic_fault: "유압 공급 저하", downstream_block: "출측 코일 정체"})[s.scenario_id] || s.scenario_id;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push({ id: s.scenario_id, title: title.replace(`${key} · `, "") });
    }
    return groups;
  }
  function renderScenarioPicker(config, scenarioId) {
    const groups = scenarioGroups(config);
    const current = [...groups].find(([, list]) => list.some(s => s.id === scenarioId))?.[0];
    const key = pickedScenarioGroup && groups.has(pickedScenarioGroup) ? pickedScenarioGroup : current || [...groups.keys()][0];
    setView("#scenario-equipment", [...groups.keys()].map(g => `<option value="${escape(g)}">${escape(g)}</option>`).join(""));
    $("#scenario-equipment").value = key || "";
    const inGroup = (groups.get(key) || []).some(s => s.id === scenarioId);
    setView("#scenario", (inGroup ? "" : `<option value="" disabled>${scenarioId === "normal" ? "정상 운전 · 시나리오 선택" : "시나리오 선택"}</option>`)
      + (groups.get(key) || []).map(s => `<option value="${escape(s.id)}">${escape(s.title)}</option>`).join(""));
    $("#scenario").value = inGroup ? scenarioId : "";
  }
  function renderSnapshot(snapshot, config) {
    if (!snapshot) return;
    if (snapshot.run_id !== lastSnapshot?.run_id || snapshot.scenario_id !== lastSnapshot?.scenario_id) {
      selectedPartId = null; selectedRelation="";
    }
    lastSnapshot = snapshot;
    if (!snapshot.equipment?.some((e) => e.equipment_id === selectedId)) selectedId = null;
    setText("#line-mode", label(snapshot.line_mode)); setText("#sequence", snapshot.sequence);
    setText("#diagram-state", `${mode === "live" ? "실시간" : "기록 재생"} · ${label(snapshot.line_mode)}`);
    setText("#workspace-context", `${mode === "live" ? "실시간" : "기록 재생"} · ${label(snapshot.line_mode)} · 활성 알람 ${(snapshot.active_alarms || []).length} · 선택 ${selectedId?name(selectedId, config):"없음"}`);
    setText("#alarm-count", (snapshot.active_alarms || []).length); setText("#observed-at", clock(snapshot.simulated_at));
    setText("#data-clock", `${mode === "live" ? "모의 운전 시각" : "기록 시각"}: ${clock(snapshot.simulated_at)}`);
    setText("#run-id", snapshot.run_id); setText("#coil-count", (snapshot.coils || []).length);
    const completed = mode === "live" ? history.completed : replay.events.filter((e) => e.sequence <= snapshot.sequence && e.event_type === "coil_exited").length;
    setText("#throughput", completed);
    const windowSnapshots = mode === "live" ? history.snapshots : replay.snapshots.slice(Math.max(0, replay.index - 179), replay.index + 1);
    renderOperations(snapshot, config, windowSnapshots); renderLineBoard(snapshot, config, windowSnapshots); renderUtilBars(snapshot, config, windowSnapshots);
    const configBadge = !config || replay.configPreserved === false ? "기록 재생 · 당시 구성 미보존" : "기록 재생 · 당시 구성";
    setText("#mode-badge", mode === "live" ? "실시간 · 합성 데이터" : configBadge);
    if (mode === "live") renderScenarioPicker(config, snapshot.scenario_id);
    setText("#detail-jump", selectedId ? `${name(selectedId, config)} 상세·조치 보기 →` : "설비 상세·조치 보기 →");
    if (snapshot.speed != null) $("#speed").value = String(snapshot.speed);
    renderEquipment(snapshot, config); renderDetail(snapshot, config);
    const recovery = snapshot.recovery;
    const selectedRelated = !recovery || recovery.equipment_id === selectedId || operator.buildOperatorModel(snapshot, config, selectedId).links.some(l=>l.affected && l.to_id===selectedId);
    const contextNote = recovery && recovery.equipment_id !== selectedId ? `<p class="recovery-owner">${recovery.stage === "completed" ? "최근 복구 이력" : selectedRelated ? "선택 설비의 대기를 해소할 공급·구동 설비 조치" : "다른 설비의 진행 중인 이상·복구"}: <button type="button" data-equipment="${escape(recovery.equipment_id)}">${escape(name(recovery.equipment_id, config))}</button></p>` : "";
    const recoveryHtml = contextNote + recoveryView(snapshot, mode === "live" && !stale);
    setView("#recovery-content", !selectedId ? '<p>설비를 선택하면 관련 조치와 복구 이력을 표시합니다.</p>' : recovery?.stage === "completed" ? `<details><summary>최근 복구 이력 · ${escape(recovery.title)} · 완료</summary>${recoveryHtml}</details>` : recoveryHtml);
    setText("#component-equipment", name(selectedId, config));
    setView("#component-content", componentView(snapshot, selectedId));
    // 부품 기록이 없으면 위 부품 위치도가 이미 "기록 없음"을 말한다 — 같은 말을 두 번 하지 않는다
    if ($("#component-panel")) $("#component-panel").hidden = !(snapshot.components || []).some(c => c.equipment_id === selectedId);
    updateControls();
    setView("#alarm-list", (snapshot.active_alarms || []).map(a=>`<li class="${a.severity === "critical" ? "fault" : "warning"}"><button type="button" data-equipment="${escape(a.equipment_id)}">${escape(label(a.severity))} · ${escape(name(a.equipment_id, config))} · ${escape(a.label || a.code)}</button><small>${escape(a.code)}</small><small>발생 ${escape(clock(a.raised_at))}</small></li>`).join("") || '<li>활성 알람 없음</li>');
    const events = mode === "live" ? history.events : replay.events.filter((e) => e.sequence <= snapshot.sequence);
    setView("#event-list", events.slice(-25).reverse().map(e=>`<li><b>${escape(eventText(e, config))}</b><small>${escape(clock(e.occurred_at))}</small>${e.observation ? `<details><summary>원문 기록</summary><p>${escape(e.observation)}</p></details>` : ""}</li>`).join("") || '<li>이벤트 없음</li>');
    for (const format of ["jsonl", "csv"]) { const link = $(`#export-${format}`); link.href = `/api/export?run_id=${encodeURIComponent(snapshot.run_id)}&format=${format}`; link.download = `${snapshot.run_id}.${format}`; }
  }
  async function refresh() {
    if (mode !== "live" || loading) return;
    loading = true; const epoch = requestEpoch;
    try {
      if (!liveConfig.config) liveConfig.config = (await request("/api/config")).config;
      const snapshot = await request("/api/state");
      if (snapshot.config_id !== liveConfig.configId) {
        liveConfig = createConfigCache();
        liveConfig.config = (await request("/api/config")).config;
        liveConfig.configId = snapshot.config_id;
      }
      if (epoch !== requestEpoch || mode !== "live") return;
      const previous = history.snapshots.at(-1);
      if (!previous || previous.run_id !== snapshot.run_id || previous.sequence !== snapshot.sequence || snapshot.line_mode === "paused") lastAdvance = Date.now();
      acceptSnapshot(history, snapshot);
      const payload = await request(`/api/events?after_sequence=${Math.max(-1, history.cursor - 1)}`);
      if (epoch !== requestEpoch || mode !== "live") return;
      payload.events = (payload.events || []).filter((event) => event.sequence <= snapshot.sequence);
      if (!acceptEvents(history, payload)) { setConnection("새 실행 동기화 중"); return; }
      lastReceived = Date.now();
      const stalled = !["paused", "stopped"].includes(snapshot.line_mode) && Date.now() - lastAdvance > 10000;
      stale = stalled; renderSnapshot(snapshot, liveConfig.config);
      if (stalled) freezeCoils();
      setConnection(stalled ? "운전 데이터 진행 지연" : connectionState(lastReceived, Date.now(), snapshot.line_mode), stalled ? "warning" : "");
    } catch (error) { if (epoch === requestEpoch && mode === "live") { stale=true; setConnection(`연결 실패 · 마지막 관측 표시 · ${error.message}`, "fault"); freezeCoils(); updateControls(); } }
    finally { loading = false; }
  }
  function freezeCoils() { document.querySelectorAll(".is-moving").forEach(node => node.classList.remove("is-moving")); document.querySelectorAll(".coil,.flow-coil").forEach((node) => { node.style.transition = "none"; }); }
  function updateControls() {
    document.querySelectorAll("#control-panel button, #control-panel select, #recovery-panel [data-action], #recovery-panel [data-command]").forEach((el) => { el.disabled = mode !== "live" || controlPending || stale; });
    const plan = lastSnapshot?.recovery, stage = plan?.stage, optional = plan?.required === false;
    document.querySelectorAll('[data-command="recover"]').forEach(recover=>{ recover.disabled = mode !== "live" || controlPending || stale || lastSnapshot?.scenario_id === "normal" || (stage && stage !== "ready" && !(optional && stage === "actions")); });
    const locked = stage === "stabilizing" || (stage && stage !== "completed" && !optional);
    if (locked) { $("#scenario").disabled = true; if ($("#scenario-equipment")) $("#scenario-equipment").disabled = true; }
    if ($("#scenario-lock")) $("#scenario-lock").hidden = !locked || mode !== "live";
    // 시작·일시정지·재개를 버튼 하나로: 멈춰 있으면 시작(재개), 돌고 있으면 일시정지
    const lineMode = lastSnapshot?.line_mode, halted = !lineMode || lineMode === "paused" || lineMode === "stopped";
    const toggle = $("#run-toggle"), state = $("#run-state");
    if (toggle?.dataset) {
      toggle.dataset.command = halted ? "start" : "pause";
      toggle.textContent = halted ? (lineMode === "paused" ? "▶ 재개" : "▶ 시작") : "⏸ 일시정지";
      toggle.classList?.toggle("primary-button", halted);
    }
    if (state?.dataset) { state.textContent = lineMode ? `● ${label(lineMode)}` : "—"; state.dataset.mode = lineMode || ""; }
    setText("#control-status", mode !== "live" ? "기록 조회 중 · 시뮬레이션 제어 잠금" : stale ? "데이터 연결 확인 후 제어 가능" : `현재 ${label(lineMode)} · 모의 운전 전용`);
    setText("#recover-hint", mode !== "live" ? "기록 조회 중에는 복구할 수 없습니다." : stale ? "데이터 연결 확인이 필요합니다." : stage === "completed" ? "복구가 완료되었습니다." : !plan ? "복구할 이상이 없습니다." : stage === "stabilizing" ? "안정화 관찰 중입니다." : stage !== "ready" && !optional ? "필수 조치 기록 후 복구할 수 있습니다." : "모의 복구를 시작할 수 있습니다.");
    document.querySelectorAll('#control-panel [data-command="recover"]').forEach(b => b.classList?.toggle("attention", !b.disabled));
  }
  async function control(command, extra = {}) {
    if (mode !== "live" || controlPending || stale) return;
    controlPending = true; updateControls();
    try { await request("/api/control", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ command, ...extra }) }); setText("#control-message", "명령이 적용되었습니다."); }
    catch (error) { setText("#control-message", `제어 실패 · ${error.message}`); pickedScenarioGroup = null; if (lastSnapshot) renderScenarioPicker(currentConfig(), lastSnapshot.scenario_id); }
    finally { controlPending = false; updateControls(); await refresh(); }
  }
  async function loadRuns() {
    const payload = await request("/api/runs"), select = $("#replay-run"), previous = select.value;
    select.innerHTML = (payload.runs || []).slice().sort((a,b)=>Date.parse(b.started_at)-Date.parse(a.started_at)).map((run) => `<option value="${escape(run.run_id)}">${escape(clock(run.started_at))} · ${escape(run.run_id.slice(0, 10))}</option>`).join("");
    if ([...select.options].some((o) => o.value === previous)) select.value = previous;
    if (!select.options.length) setText("#replay-position", "저장된 실행이 없습니다.");
  }
  async function loadReplay() {
    if (mode !== "replay") return;
    const runId = $("#replay-run").value; if (!runId) return;
    const epoch = ++requestEpoch; replay.playing = false;
    clearDisplay("기록 불러오는 중");
    try {
      const payload = await request(`/api/runs/${encodeURIComponent(runId)}/replay?sequence=-1`);
      if (epoch !== requestEpoch || mode !== "replay") return;
      replay = { snapshots: payload.snapshots || [], events: payload.events || [], index: 0, playing: false, configId: payload.config_id, configPreserved: payload.config_preserved !== false };
      if (!replay.configId) replayConfig = createConfigCache();
      if (replay.configId) {
        if (!configsCompatible(replayConfig, { config_id: replay.configId })) {
          try { replayConfig = { config: (await request(`/api/configs/${encodeURIComponent(replay.configId)}`)).config, configId: replay.configId }; }
          catch { replayConfig = { config: null, configId: replay.configId }; }
        }
      }
      $("#replay-sequence").max = String(Math.max(0, replay.snapshots.length - 1)); renderReplay();
      setView("#replay-event", '<option value="">이벤트 시점으로 이동</option>' + replay.events.filter(e=>["alarm_raised","recovery_started","recovered","alarm_cleared"].includes(e.event_type)).map(e=>`<option value="${e.sequence}">${escape(clock(e.occurred_at))} · ${escape(eventText(e,replayConfig.config))}</option>`).join(""));
    } catch (error) { if (epoch === requestEpoch) setConnection(`재생 조회 실패 · ${error.message}`, "fault"); }
  }
  function renderReplay() {
    $("#replay-play").textContent = replay.playing ? "재생 일시정지" : "기록 재생";
    $("#replay-sequence").value = String(replay.index); $("#replay-play").disabled = !replay.snapshots.length;
    if (!replay.snapshots.length) { clearDisplay("저장된 스냅샷이 없습니다."); setText("#replay-position", "저장된 스냅샷이 없습니다."); setConnection("재생할 기록 없음", "warning"); return; }
    renderSnapshot(replay.snapshots[replay.index], replayConfig.config); setText("#replay-position", `${clock(lastSnapshot.simulated_at)} · ${replay.index + 1} / ${replay.snapshots.length} · 순번 ${lastSnapshot.sequence}`);
    setConnection(replay.playing ? "기록 재생 중 · 실시간 제어 분리" : "기록 재생 일시정지 · 실시간 제어 분리");
  }
  function clearDisplay(message) {
    setText("#workspace-context", message);
    setText("#data-clock", message);
    setView("#replay-event", '<option value="">이벤트 시점으로 이동</option>');
    setText("#selected-connection", "연결 정보 불러오는 중");
    lastSnapshot = null; $("#line-map").replaceChildren();
    for (const id of ["line-map", "equipment-detail", "incident-summary", "part-locator", "selection-evidence", "recovery-content", "component-content", "alarm-list"]) { delete $(`#${id}`).dataset.html; setText(`#${id}`, message); }
    delete $("#line-map").dataset.layout;
    setText("#process-story", message);
    for (const id of ["line-mode", "sequence", "alarm-count", "observed-at", "run-id", "coil-count", "throughput"]) setText(`#${id}`, "—");
    for (const id of ["equipment-detail", "sensor-trends", "alarm-list", "event-list"]) setText(`#${id}`, message);
    for (const id of ["line-board", "util-bars", "operations-body", "utility-links"]) { delete $(`#${id}`).dataset.html; $(`#${id}`).replaceChildren(); }
    setText("#recovery-content", message); delete $("#recovery-content").dataset.view; setText("#component-content", message);
    for (const format of ["jsonl", "csv"]) $(`#export-${format}`).removeAttribute("href");
    setText("#mode-badge", mode === "live" ? "실시간 · 합성 데이터" : "기록 재생 · 합성 데이터");
  }
  async function validateConfig(draft) {
    try {
      const result = await request("/api/config/validate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ draft }) });
      return result;
    } catch (error) {
      return { valid: false, errors: [error.message], is_synthetic: true };
    }
  }
  function describeDiffItem(item) {
    if (typeof item !== "object" || item === null) return escape(item);
    if (item.error) return escape(item.error);
    const head = escape(item.equipment_id || "");
    if (item.old_asset_id) return `${head}: ${escape(item.old_asset_id)} → ${escape(item.new_asset_id)}`;
    if (item.signal) return `${head} ${escape(item.signal)}${item.change === "unit" ? ` 단위 ${escape(item.old_unit)} → ${escape(item.new_unit)}` : ` (${escape(item.change || "변경")})`}`;
    if (item.old_route) return `${(item.old_route || []).join("→")} ⇒ ${(item.new_route || []).join("→")}`;
    if (item.old_name !== undefined) return `${head}: ${escape(item.old_name)} → ${escape(item.new_name)}${item.old_profile !== item.new_profile ? ` (프로필 ${escape(item.old_profile)} → ${escape(item.new_profile)})` : ""}`;
    if (item.code) return `${head} (${escape(item.code)})`;
    return escape(JSON.stringify(item));
  }
  function renderConfigDiff(diff) {
    const lines = [];
    for (const [type, items] of Object.entries(diff || {})) {
      if (Array.isArray(items) && items.length) {
        const typeLabel = { renamed: "이름 변경", param_changed: "파라미터 변경", asset_replaced: "자산 교체", added: "추가", removed: "제거", signal_changed: "신호 변경", route_changed: "경로 변경", layout_changed: "배치 변경" }[type] || type;
        lines.push(`<li><b>${typeLabel}</b>: ${items.map(describeDiffItem).join(", ")}</li>`);
      }
    }
    return lines.length ? `<ul>${lines.join("")}</ul>` : "변경 없음";
  }
  async function applyConfig() {
    if (mode !== "live" || applyPending) return;
    const fileInput = $("#config-file");
    if (!fileInput.files.length) { setText("#config-message", "파일을 선택하세요."); return; }
    const file = fileInput.files[0];
    let draft;
    try {
      draft = JSON.parse(await file.text());
    } catch (e) {
      setText("#config-message", `파일 파싱 오류: ${e.message}`);
      return;
    }
    const validation = await validateConfig(draft);
    if (!validation.valid) {
      const errors = (validation.errors || []).map((e) => `<li>${escape(e)}</li>`).join("");
      $("#config-errors").innerHTML = errors ? `<ul>${errors}</ul>` : "알 수 없는 오류";
      return;
    }
    $("#config-errors").innerHTML = `<p>검증 완료</p>${renderConfigDiff(validation.diff)}`;
    const reason = $("#config-reason").value || "(이유 미입력)";
    const actor = $("#config-actor").value || "작업자(미입력)";
    applyPending = true; setText("#config-message", "적용 중...");
    try {
      const result = await request("/api/config/apply", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ base_config_id: liveConfig.configId, draft, reason, actor }) });
      setText("#config-message", `적용 성공. 새 실행: ${escape(result.run_id)}`);
      fileInput.value = "";
      $("#config-reason").value = "";
      liveConfig = createConfigCache();
      await refresh();
    } catch (error) {
      if (error.message.includes("409")) setText("#config-message", "구성 충돌 또는 가동 중: 일시정지 후 다시 시도하세요.");
      else if (error.message.includes("400")) setText("#config-message", `검증 오류: ${error.message}`);
      else setText("#config-message", `적용 오류: ${error.message}`);
    } finally { applyPending = false; }
  }
  $("#view-mode").onchange = async (event) => {
    mode = event.target.value; requestEpoch++; replay.playing = false; freezeCoils(); clearDisplay("데이터 불러오는 중");
    $("#replay-controls").hidden = mode !== "replay"; $("#config-panel").hidden = mode !== "live"; updateControls();
    try { if (mode === "replay") { await loadRuns(); await loadReplay(); } else { history = createHistory(); await refresh(); } }
    catch (error) { setConnection(`조회 실패 · ${error.message}`, "fault"); }
  };
  $("#replay-run").onchange = loadReplay;
  $("#replay-refresh").onclick = async () => { try { await loadRuns(); await loadReplay(); } catch (error) { setConnection(error.message, "fault"); } };
  $("#replay-play").onclick = () => { if (replay.index >= replay.snapshots.length - 1) replay.index = 0; replay.playing = !replay.playing; renderReplay(); };
  $("#replay-sequence").oninput = (event) => { replay.index = Number(event.target.value); replay.playing = false; renderReplay(); };
  $("#replay-event").onchange = event => {
    if (!event.target.value) return;
    const index = replay.snapshots.findIndex(s=>s.sequence >= Number(event.target.value));
    if (index < 0) return;
    replay.index = index; replay.playing = false; renderReplay();
  };
  $("#operations-filter").onchange = () => renderSnapshot(lastSnapshot, currentConfig());
  $("#signal-select").onchange = () => renderTrend(mode === "live" ? liveConfig.config : replayConfig.config);
  $("#animate-machines").onchange = () => renderSnapshot(lastSnapshot, mode === "live" ? liveConfig.config : replayConfig.config);
  $("#config-validate").onclick = async () => {
    const fileInput = $("#config-file");
    if (!fileInput.files.length) { setText("#config-message", "파일을 선택하세요."); return; }
    const file = fileInput.files[0];
    let draft;
    try { draft = JSON.parse(await file.text()); }
    catch (e) { setText("#config-message", `파일 파싱 오류: ${e.message}`); return; }
    const validation = await validateConfig(draft);
    if (!validation.valid) {
      const errors = (validation.errors || []).map((e) => `<li>${escape(e)}</li>`).join("");
      $("#config-errors").innerHTML = errors ? `<ul>${errors}</ul>` : "검증 실패";
    } else {
      $("#config-errors").innerHTML = `<p>검증 완료</p>${renderConfigDiff(validation.diff)}`;
    }
  };
  $("#config-apply").onclick = applyConfig;
  // 새 실행은 쌓인 운영 지표와 진행 중 사건을 지운다 — 3초 안에 한 번 더 눌러야 실행한다(모든 탭에 바가 보여 잘못 누르기 쉽다).
  let resetArmed = null;
  const disarmReset = (button) => { clearTimeout(resetArmed); resetArmed = null; button.classList.remove("attention"); };
  document.querySelectorAll("#control-panel [data-command]").forEach((button) => { button.onclick = () => {
    if (button.dataset.command === "reset") {
      if (!resetArmed) {
        button.classList.add("attention");   // 주황 테두리 = 한 번 더 누르면 실행
        setText("#control-message", "새 시뮬레이션을 시작하려면 3초 안에 한 번 더 누르세요. 현재 실행은 이력에 보존됩니다.");
        resetArmed = setTimeout(() => disarmReset(button), 3000);
        return;
      }
      disarmReset(button);
    }
    control(button.dataset.command);
  }; });
  $("#speed").onchange = (event) => control("speed", { speed: Number(event.target.value) });
  $("#scenario-equipment").onchange = (event) => { pickedScenarioGroup = event.target.value; if (lastSnapshot) renderScenarioPicker(currentConfig(), lastSnapshot.scenario_id); };
  $("#scenario").onchange = (event) => { pickedScenarioGroup = null; control("scenario", { scenario_id: event.target.value }); };
  document.addEventListener("click", event => {
    const tab=event.target.closest("[data-workspace]"); if (tab) showWorkspace(tab.dataset.workspace);
    const jump=event.target.closest("[data-open-workspace]"); if (jump) { showWorkspace(jump.dataset.openWorkspace, true); if (jump.dataset.openWorkspace==="detail") $("#equipment-detail").focus(); }
    const eq=event.target.closest("[data-equipment]"); if (eq) selectEquipment(eq.dataset.equipment,eq.dataset.relation || "",Boolean(eq.closest("#incident-summary,#equipment-results,#alarm-list,#line-board,#operations-body,#util-bars,#equipment-detail")));
    const part=event.target.closest("[data-part]"); if (part) { selectedPartId=part.dataset.part; renderSnapshot(lastSnapshot,currentConfig()); }
    const action=event.target.closest("#recovery-content [data-action]"); if (action && !action.disabled) control("recovery_action",{action_id:action.dataset.action});
    const command=event.target.closest("#recovery-content [data-command]"); if (command && !command.disabled) control(command.dataset.command);
  });
  $("#line-map").addEventListener("keydown", event=>{ if (["Enter"," "].includes(event.key) && event.target.matches('[role="button"]')) { event.preventDefault(); selectEquipment(event.target.dataset.equipment,event.target.dataset.relation || ""); } });
  $("#workspace-flow").addEventListener("keydown",event=>{ if(event.key==="Escape") { event.preventDefault(); if ($("#diagram-legend").open) $("#diagram-legend").open=false; else clearSelection(); } });
  $("#clear-selection").onclick=clearSelection;
  $("#workspace-tabs").addEventListener("keydown", workspaceKeydown);
  $("#experience-mode").onchange=()=>{ document.body.dataset.experience=$("#experience-mode").value; $(".learning-guide").open=$("#experience-mode").value==="learn"; renderSnapshot(lastSnapshot,currentConfig()); };
  $("#relation-filter").onchange=()=>renderSnapshot(lastSnapshot,currentConfig());
  $("#map-scale").onchange=event=>{
    const expanded=event.target.value==="detail";
    $(".map-scroll").classList.toggle("map-expanded",expanded);
    $("#diagram-zoom").textContent=expanded?"전체 맞춤":"확대";
    $("#diagram-zoom").setAttribute("aria-pressed",String(expanded));
  };
  $("#diagram-open").onclick=()=>setDiagramMode(true);
  $("#diagram-back").onclick=()=>setDiagramMode(false);
  $("#diagram-clear").onclick=clearSelection;
  $("#diagram-zoom").onclick=()=>{
    $("#map-scale").value=$("#map-scale").value==="detail"?"fit":"detail";
    $("#map-scale").onchange({target:$("#map-scale")});
  };
  $("#equipment-search").oninput=event=>{
    const query=event.target.value.trim().toLowerCase();
    const matches=(currentConfig()?.equipment || []).filter(e=>[e.code,e.name,e.equipment_id,roleFor(e)[0]].join(" ").toLowerCase().includes(query));
    setView("#equipment-results",query ? matches.map(e=>`<button type="button" data-equipment="${escape(e.equipment_id)}">${escape(e.code)} · ${escape(roleFor(e)[0])}</button>`).join("") || '<p role="status">일치하는 설비 없음</p>' : "");
  };
  $("#download-context").onclick=()=>{
    if (!lastSnapshot || !selectedId) return setText("#context-message","설비를 먼저 선택하세요.");
    const draft=operator.contextDraft(operator.buildOperatorModel(lastSnapshot,currentConfig(),selectedId,selectedPartId),mode,mode==="live"&&stale);
    const url=URL.createObjectURL(new Blob([JSON.stringify(draft,null,2)],{type:"application/json"}));
    const link=document.createElement("a"); link.href=url; link.download=`shiftlink-context-${lastSnapshot.sequence}.json`; link.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
    setText("#context-message","설비 확인 보고서 초안을 내려받았습니다. 미확인 항목은 인계 전 확인하세요.");
  };
  $("#config-panel").hidden=false;
  if (globalThis.location && new URLSearchParams(globalThis.location.search).get("view")!=="full") setDiagramMode(true,false);
  // PDA 키오스크에서 열었으면(파이가 ?from=pda로 보냄) 주소창이 없으니 돌아가기·재시작 버튼을 보인다
  if (globalThis.location && new URLSearchParams(globalThis.location.search).get("from")==="pda") $("#kiosk-bar").hidden = false;
  refresh();
  const tickClock = () => { const d = new Date(), p = (n) => String(n).padStart(2, "0"); setText("#board-clock", `${d.getFullYear()}/${p(d.getMonth() + 1)}/${p(d.getDate())}  ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`); };
  tickClock();
  setInterval(() => {
    tickClock();
    if (mode === "live") { if (lastReceived && Date.now() - lastReceived > 10000) { stale=true; setConnection("데이터 수신 지연 · 마지막 관측 표시 · 시연 조치 잠금", "warning"); freezeCoils(); updateControls(); } refresh(); }
    else if (replay.playing) { replay.index = Math.min(replay.index + 1, replay.snapshots.length - 1); if (replay.index === replay.snapshots.length - 1) replay.playing = false; renderReplay(); }
  }, 1000);
})();
