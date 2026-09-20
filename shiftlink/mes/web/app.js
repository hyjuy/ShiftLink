(() => {
  const labels = { running: "가동", paused: "일시정지", stopped: "정지", waiting: "대기", fault: "이상", recovering: "복구 관찰", warning: "주의", critical: "고장", normal: "정상", recovery: "복구 중", downstream_block: "하류 정체", upstream_drive_fault: "상류 구동 이상", hydraulic_supply_low: "유압 공급 저하", self_fault: "자체 이상", material_shortage: "소재 부족", planned_stop: "계획 정지" };
  const label = (value) => labels[value] || value || "—";
  labels.quality_hold = "제품 검사·보류";
  const relationLabels = { material_flow: "소재 이송", utility_supply: "유틸리티 공급", hydraulic_supply: "유압 공급", pneumatic_supply: "공압 공급", power_supply: "전력 공급", mechanical_drive: "기계 구동", drive: "구동", interlock: "인터록", common_mode: "공통 영향", co_occurrence: "동시 발생 관계" };
  const escape = (value) => String(value ?? "—").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
  const stateClass = (item) => item.fault_level === "warning" ? "warning" : item.fault_level && item.fault_level !== "normal" ? "fault" : item.operating_state === "waiting" ? "waiting" : item.operating_state === "stopped" ? "stopped" : "normal";
  const statusText = (item) => [label(item.operating_state), label(item.fault_level), item.wait_reason && label(item.wait_reason)].filter(Boolean).join(" · ");
  const clock = (value) => value ? new Date(value).toLocaleString("ko-KR", { hour12: false }) : "—";
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
    if (!plan) return '<p class="empty-state">감속기 과열 · 유압유 과열 · 감속기 누유 · 영향 코일 검사·보류 시나리오를 선택하면 필요한 조치와 복귀 조건을 볼 수 있습니다.</p>';
    const done = plan.stage === "completed", next = plan.actions.findIndex(a => !a.completed);
    const steps = [{title: "이상 발생", done: true}, ...plan.actions.map((a, i) => ({title:a.title, done:a.completed, current:plan.stage === "actions" && i === next})),
      {title: "안정화 관찰", done, current:plan.stage === "stabilizing"}, {title: "정상 복귀", done, current:done}];
    const flow = steps.map((s, i) => `<li class="${s.done ? "done" : ""} ${s.current ? "current" : ""}" ${s.current ? 'aria-current="step"' : ''}><span>${s.done ? "✓" : i + 1}</span><b>${escape(s.title)}</b><small>${s.current ? "현재 단계" : s.done ? "완료" : "대기"}</small></li>`).join("");
    const action = plan.stage === "actions" ? plan.actions[next] : null;
    const status = done ? "정상 복귀 완료" : plan.stage === "ready" ? "필수 조치 완료 · 복귀 진행을 눌러 안정화 관찰을 시작하세요." : plan.stage === "stabilizing" ? `안정화 관찰 중 · ${plan.remaining_ticks} tick 남음${snapshot.line_mode === "paused" ? " · 재개 버튼을 누르세요." : ""}` : "다음 조치를 완료해야 복귀할 수 있습니다.";
    const held = (snapshot.coils || []).filter(c => c.quality_status === "hold");
    const source = /^https:\/\//.test(plan.source_url || "") ? `<a href="${escape(plan.source_url)}" target="_blank" rel="noopener noreferrer">근거 매뉴얼 ↗</a>` : "";
    return `<div class="recovery-heading"><h3>${escape(plan.title)}</h3>${source}</div><ol class="recovery-flow" aria-label="정상 복귀 단계">${flow}</ol><p class="recovery-status">${escape(status)}</p>${action ? `<div class="next-action"><div><b>${escape(action.title)}</b><p>${escape(action.detail)}</p></div>${interactive ? `<button type="button" class="primary-button" data-action="${escape(action.action_id)}">조치 완료 (모의)</button>` : '<span class="hint">기록 조회 전용</span>'}</div>` : ""}${interactive && plan.stage === "ready" ? '<button type="button" class="primary-button" data-command="recover">복귀 진행 · 안정화 시작</button>' : ""}${interactive && snapshot.line_mode === "paused" ? '<button type="button" data-command="resume">모의 운전 재개</button>' : ""}${held.length ? `<p class="held-coils">보류 코일 ${held.length}개 · ${held.map(c => escape(c.coil_id)).join(" · ")}</p>` : ""}`;
  }
  function componentView(snapshot, equipmentId) {
    const parts = (snapshot.components || []).filter(c => c.equipment_id === equipmentId);
    if (!parts.length) return '<p class="hint">부품 상태 기록 없음 · 이 설비 또는 과거 실행에는 모의 내구도 정보가 없습니다.</p>';
    return `<div class="component-list">${parts.map(c => {
      const value = Math.max(0, Math.min(100, Number(c.health_percent))), state = value < 40 ? "점검 필요" : value < 70 ? "주의" : "양호";
      return `<article class="component-card ${value < 40 ? "degraded" : ""}"><div><b>${escape(c.name)}</b><strong>${value.toFixed(1)}% · ${state}</strong></div><meter min="0" max="100" low="40" high="70" optimum="100" value="${value}" aria-label="${escape(c.name)} 모의 건전도">${value.toFixed(1)}%</meter><small>누적 운전 ${(c.operating_seconds / 3600).toFixed(3)} h · 정비 ${Number(c.maintenance_count)}회${c.last_maintenance_at ? ` · 최근 ${escape(clock(c.last_maintenance_at))}` : ""}</small></article>`;
    }).join("")}</div>`;
  }
  if (typeof module !== "undefined") module.exports = { createHistory, acceptSnapshot, acceptEvents, connectionState, stateClass, equipmentKind, machineMoving, processMessage, recoveryView, componentView };
  if (typeof document === "undefined") return;
  const operator = globalThis.MesOperator;
  const $ = (selector) => document.querySelector(selector);
  const setText = (selector, value) => { const el = $(selector); if (el) el.textContent = value; };
  let selectedId = null, lastSnapshot = null, mode = "live", lastReceived = 0, lastAdvance = 0;
  let selectedRelation = "", selectedPartId = null, incidentSignature = "", stale = true;
  let history = createHistory(), requestEpoch = 0, loading = false, controlPending = false, applyPending = false;
  let liveConfig = createConfigCache(), replayConfig = createConfigCache();
  let replay = { snapshots: [], events: [], index: 0, playing: false, configId: null, configPreserved: true };
  function setConnection(message, kind = "") { setText("#connection-status", message); $("#connection-status").className = `status-label ${kind}`; }
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
      const target = [...el.querySelectorAll('button,[role="button"]')].find(n=>keys.every(([k,v])=>n.getAttribute(k)===v)) || el.querySelector('[data-action],[data-command="recover"],button');
      (target || $("#equipment-detail"))?.focus({preventScroll:true});
    }
  }
  const currentConfig = () => mode === "live" ? liveConfig.config : replayConfig.config;
  function showWorkspace(key, focus = false) {
    const target = document.querySelector(`#tab-${key}`);
    if (!target?.dataset?.workspace) return;
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
    selectedId=id; selectedPartId=null; selectedRelation=relation; renderSnapshot(lastSnapshot,currentConfig());
    if (move) { showWorkspace("detail"); $("#equipment-detail").focus(); $("#equipment-detail").scrollIntoView({block:"start"}); }
    setText("#operator-announcement", `${name(id,currentConfig())} 선택. 상세 영역에서 부품과 관측 근거를 확인하세요.`);
  }
  function renderEquipment(snapshot, config) {
    const model=operator.buildOperatorModel(snapshot,config,selectedId,selectedPartId);
    const relation=model.links.find(l=>operator.relationKey(l)===selectedRelation);
    setText("#selected-connection", relation ? `${relation.from.code || relation.from_id} → ${relation.to.code || relation.to_id} · ${relation.label} · ${relation.affected ? "관측된 영향 대기" : "구성상 연결 · 원인 확정 아님"}` : "연결선을 선택하면 출발·도착 설비와 관계를 확인할 수 있습니다.");
    setText("#process-story",processMessage(snapshot,config));
    setView("#line-map",operator.flowView(model,$("#experience-mode").value,$("#relation-filter").value,selectedRelation));
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
    setView("#part-locator",operator.partView(model));
    setView("#selection-evidence",operator.evidenceView(model,selectedRelation));
    setView("#utility-links",model.links.filter(l=>l.relation_type!=="material_flow").map(l=>`<p><button type="button" data-equipment="${escape(l.from_id)}">${escape(l.from.code || l.from_id)}</button> → <button type="button" data-equipment="${escape(l.to_id)}">${escape(l.to.code || l.to_id)}</button> · ${escape(l.label)}</p>`).join("") || "연결 정보 없음");
    const signature=JSON.stringify([snapshot.run_id,model.faults.map(n=>n.equipment_id),model.held.map(c=>c.coil_id),snapshot.recovery?.stage]);
    if (signature!==incidentSignature) { incidentSignature=signature; setText("#operator-announcement",`상태 변경. 자체 이상·주의 ${model.faults.length}대, 보류 코일 ${model.held.length}개. 지금 확인할 위치에서 상세를 선택하세요.`); }
  }
  function renderDetail(snapshot, config) {
    const equipment = snapshot.equipment?.find((item) => item.equipment_id === selectedId);
    const measurements = (snapshot.measurements || []).filter((item) => item.equipment_id === selectedId);
    const configEq = config?.equipment?.find((e) => e.equipment_id === selectedId);
    if (!equipment) { $("#equipment-detail").innerHTML = "<h2>설비 상세</h2><p>설비 정보가 없습니다.</p>"; return; }
    const configInfo = config ? `<p class="config-ref">구성 <small>${config.version_label || config.config_id?.slice(0, 8)}</small></p>` : "";
    const assetInfo = configEq?.asset_id ? `<p>자산 ID: ${escape(configEq.asset_id)}</p>` : "";
    const profileInfo = configEq?.profile_id ? `<p>프로필: ${escape(configEq.profile_id)}</p>` : "";
    setView("#equipment-detail", `<p class="eyebrow">SELECTED EQUIPMENT</p><h2>${escape(configEq?.code || selectedId)} · ${escape(roleFor(configEq)[0])}</h2><p class="selected-state">${escape(statusText(equipment))}</p><details><summary>설비 식별 정보</summary><p>${escape(name(selectedId, config))} · ${escape(selectedId)}</p>${assetInfo}${profileInfo}${configInfo}</details>`);
    const select = $("#signal-select"), signature = (configEq?.signals || []).map((s) => s.signal).join("|");
    if (select.dataset.signals !== signature) {
      select.innerHTML = (configEq?.signals || []).map((s) => `<option value="${escape(s.signal)}">${escape(s.name || s.signal)} (${escape(s.unit)})</option>`).join("");
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
    const unit = values.find((p) => p.measurement)?.measurement?.unit || "";
    const description = `${signal} · ${numbers.length}개 관측 · 최소 ${min} / 최대 ${max} ${unit} · ${clock(values[0].time)} ~ ${clock(values.at(-1).time)}`;
    $("#sensor-trends").innerHTML = coordinates ? `<svg viewBox="0 0 420 150" role="img" aria-label="${escape(description)}"><title>${escape(description)}</title><path d="M35 15 V125 H410" fill="none" stroke="currentColor" opacity=".4"/><polyline points="${coordinates}" fill="none" stroke="#53dfc6" stroke-width="3"/><text x="3" y="20" fill="currentColor" font-size="10">${max}</text><text x="3" y="123" fill="currentColor" font-size="10">${min}</text></svg>` : `<p class="empty-state">추이 데이터 없음</p>`;
    setText("#trend-description", description);
  }
  function renderFeed(selector, items, format) { $(selector).innerHTML = items.length ? items.map((item) => `<li class="${item.severity === "critical" ? "fault" : ""}">${escape(format(item))}</li>`).join("") : "<li>없음</li>"; }
  function renderSnapshot(snapshot, config) {
    if (!snapshot) return;
    if (snapshot.run_id !== lastSnapshot?.run_id || snapshot.scenario_id !== lastSnapshot?.scenario_id) {
      selectedId = snapshot.equipment?.find(e => e.fault_level !== "normal")?.equipment_id || snapshot.recovery?.equipment_id || selectedId;
      selectedPartId = null; selectedRelation="";
    }
    lastSnapshot = snapshot;
    if (!snapshot.equipment?.some((e) => e.equipment_id === selectedId)) selectedId = snapshot.equipment?.[0]?.equipment_id;
    setText("#line-mode", label(snapshot.line_mode)); setText("#sequence", snapshot.sequence);
    setText("#workspace-context", `${mode === "live" ? "실시간" : "기록 재생"} · ${label(snapshot.line_mode)} · 활성 알람 ${(snapshot.active_alarms || []).length} · 선택 ${name(selectedId, config)}`);
    setText("#alarm-count", (snapshot.active_alarms || []).length); setText("#observed-at", clock(snapshot.simulated_at));
    setText("#run-id", snapshot.run_id); setText("#coil-count", (snapshot.coils || []).length);
    setText("#throughput", mode === "live" ? history.completed : replay.events.filter((e) => e.sequence <= snapshot.sequence && e.event_type === "coil_exited").length);
    const configBadge = !config || replay.configPreserved === false ? "기록 재생 · 당시 구성 미보존" : "기록 재생 · 당시 구성";
    setText("#mode-badge", mode === "live" ? "실시간 · 합성 데이터" : configBadge);
    if (mode === "live") setView("#scenario", '<option value="normal" disabled>정상 운전</option>' + (config?.scenarios || []).filter(s => s.scenario_id !== "normal").map((s) => `<option value="${escape(s.scenario_id)}">${escape(s.title || ({drive_fault: "구동부 진동 이상", hydraulic_fault: "유압 공급 저하", downstream_block: "출측 코일 정체"})[s.scenario_id] || s.scenario_id)}</option>`).join(""));
    if (snapshot.scenario_id) $("#scenario").value = snapshot.scenario_id;
    if (snapshot.speed != null) $("#speed").value = String(snapshot.speed);
    renderEquipment(snapshot, config); renderDetail(snapshot, config);
    const recovery = snapshot.recovery;
    const selectedRelated = !recovery || recovery.equipment_id === selectedId || operator.buildOperatorModel(snapshot, config, selectedId).links.some(l=>l.affected && l.to_id===selectedId);
    const contextNote = recovery && recovery.equipment_id !== selectedId ? `<p class="recovery-owner">${selectedRelated ? "선택 설비의 대기를 해소할 공급·구동 설비 조치" : "현재 선택과 별개인 진행 중 사건"}: <button type="button" data-equipment="${escape(recovery.equipment_id)}">${escape(name(recovery.equipment_id, config))}</button></p>` : "";
    setView("#recovery-content", contextNote + recoveryView(snapshot, mode === "live" && !stale));
    setText("#component-equipment", name(selectedId, config));
    setView("#component-content", componentView(snapshot, selectedId));
    updateControls();
    setView("#alarm-list", (snapshot.active_alarms || []).map(a=>`<li class="${a.severity === "critical" ? "fault" : "warning"}"><button type="button" data-equipment="${escape(a.equipment_id)}">${escape(label(a.severity))} · ${escape(name(a.equipment_id, config))} · ${escape(a.code)}</button><small>발생 ${escape(clock(a.raised_at))}</small></li>`).join("") || '<li>활성 알람 없음</li>');
    const events = mode === "live" ? history.events : replay.events.filter((e) => e.sequence <= snapshot.sequence);
    renderFeed("#event-list", events.slice(-25).reverse(), (e) => `${clock(e.occurred_at)} · ${e.event_type} · ${e.observation}`);
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
    const stage = lastSnapshot?.recovery?.stage;
    document.querySelectorAll('[data-command="recover"]').forEach(recover=>{ recover.disabled = mode !== "live" || controlPending || stale || lastSnapshot?.scenario_id === "normal" || (stage && stage !== "ready"); });
    if (stage && stage !== "completed") $("#scenario").disabled = true;
  }
  async function control(command, extra = {}) {
    if (mode !== "live" || controlPending || stale) return;
    controlPending = true; updateControls();
    try { await request("/api/control", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ command, ...extra }) }); setText("#control-message", "명령이 적용되었습니다."); }
    catch (error) { setText("#control-message", `제어 실패 · ${error.message}`); if (lastSnapshot) $("#scenario").value = lastSnapshot.scenario_id; }
    finally { controlPending = false; updateControls(); await refresh(); }
  }
  async function loadRuns() {
    const payload = await request("/api/runs"), select = $("#replay-run"), previous = select.value;
    select.innerHTML = (payload.runs || []).map((run) => `<option value="${escape(run.run_id)}">${escape(clock(run.started_at))} · ${escape(run.run_id.slice(0, 10))}</option>`).join("");
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
    } catch (error) { if (epoch === requestEpoch) setConnection(`재생 조회 실패 · ${error.message}`, "fault"); }
  }
  function renderReplay() {
    $("#replay-play").textContent = replay.playing ? "재생 일시정지" : "기록 재생";
    $("#replay-sequence").value = String(replay.index); $("#replay-play").disabled = !replay.snapshots.length;
    if (!replay.snapshots.length) { clearDisplay("저장된 스냅샷이 없습니다."); setText("#replay-position", "저장된 스냅샷이 없습니다."); setConnection("재생할 기록 없음", "warning"); return; }
    renderSnapshot(replay.snapshots[replay.index], replayConfig.config); setText("#replay-position", `${replay.index + 1} / ${replay.snapshots.length} · 순번 ${lastSnapshot.sequence}`);
    setConnection(replay.playing ? "기록 재생 중 · 실시간 제어 분리" : "기록 재생 일시정지 · 실시간 제어 분리");
  }
  function clearDisplay(message) {
    setText("#workspace-context", message);
    setText("#selected-connection", "연결 정보 불러오는 중");
    lastSnapshot = null; $("#line-map").replaceChildren();
    for (const id of ["line-map", "equipment-detail", "incident-summary", "part-locator", "selection-evidence", "recovery-content", "component-content", "alarm-list"]) { delete $(`#${id}`).dataset.html; setText(`#${id}`, message); }
    delete $("#line-map").dataset.layout;
    setText("#process-story", message);
    for (const id of ["line-mode", "sequence", "alarm-count", "observed-at", "run-id", "coil-count", "throughput"]) setText(`#${id}`, "—");
    for (const id of ["equipment-detail", "sensor-trends", "alarm-list", "event-list"]) setText(`#${id}`, message);
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
  document.querySelectorAll("#control-panel [data-command]").forEach((button) => { button.onclick = () => control(button.dataset.command); });
  $("#speed").onchange = (event) => control("speed", { speed: Number(event.target.value) });
  $("#scenario").onchange = (event) => control("scenario", { scenario_id: event.target.value });
  document.addEventListener("click", event => {
    const tab=event.target.closest("[data-workspace]"); if (tab) showWorkspace(tab.dataset.workspace);
    const jump=event.target.closest("[data-open-workspace]"); if (jump) { showWorkspace(jump.dataset.openWorkspace, true); if (jump.dataset.openWorkspace==="detail") $("#equipment-detail").focus(); }
    const eq=event.target.closest("[data-equipment]"); if (eq) selectEquipment(eq.dataset.equipment,eq.dataset.relation || "",Boolean(eq.closest("#incident-summary,#equipment-results,#alarm-list")));
    const part=event.target.closest("[data-part]"); if (part) { selectedPartId=part.dataset.part; renderSnapshot(lastSnapshot,currentConfig()); }
    const action=event.target.closest("#recovery-content [data-action]"); if (action && !action.disabled) control("recovery_action",{action_id:action.dataset.action});
    const command=event.target.closest("#recovery-content [data-command]"); if (command && !command.disabled) control(command.dataset.command);
  });
  $("#line-map").addEventListener("keydown", event=>{ if (["Enter"," "].includes(event.key) && event.target.matches('[role="button"]')) { event.preventDefault(); selectEquipment(event.target.dataset.equipment,event.target.dataset.relation || ""); } });
  $("#workspace-tabs").addEventListener("keydown", workspaceKeydown);
  $("#experience-mode").onchange=()=>{ document.body.dataset.experience=$("#experience-mode").value; $(".learning-guide").open=$("#experience-mode").value==="learn"; renderSnapshot(lastSnapshot,currentConfig()); };
  $("#relation-filter").onchange=()=>renderSnapshot(lastSnapshot,currentConfig());
  $("#equipment-search").oninput=event=>{
    const query=event.target.value.trim().toLowerCase();
    const matches=(currentConfig()?.equipment || []).filter(e=>[e.code,e.name,e.equipment_id,roleFor(e)[0]].join(" ").toLowerCase().includes(query));
    setView("#equipment-results",query ? matches.map(e=>`<button type="button" data-equipment="${escape(e.equipment_id)}">${escape(e.code)} · ${escape(roleFor(e)[0])}</button>`).join("") || '<p role="status">일치하는 설비 없음</p>' : "");
  };
  $("#download-context").onclick=()=>{
    if (!lastSnapshot) return;
    const model=operator.buildOperatorModel(lastSnapshot,currentConfig(),selectedId,selectedPartId);
    const draft={purpose:"ShiftLink 인계용 초안 · 합성 데이터 · 사람 확인 필요",view_mode:mode,stale:mode==="live"&&stale,run_id:lastSnapshot.run_id,sequence:lastSnapshot.sequence,observed_at:lastSnapshot.simulated_at,equipment:model.selected,observations:model.measurements,configured_relations:model.links.filter(l=>[l.from_id,l.to_id].includes(selectedId)),assumption:model.problemPart?`시연 가정 부품: ${model.problemPart}`:"문제 부품 미확정",unconfirmed:["실제 원인","실제 조립 위치","실제 점검 성공","안전 재가동 가능 여부"],next_check:lastSnapshot.recovery?.actions?.find(a=>!a.completed)||null,recovery:lastSnapshot.recovery,held_coils:model.held};
    const url=URL.createObjectURL(new Blob([JSON.stringify(draft,null,2)],{type:"application/json"}));
    const link=document.createElement("a"); link.href=url; link.download=`shiftlink-context-${lastSnapshot.sequence}.json`; link.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
    setText("#context-message","확인 맥락 초안을 내려받았습니다. 미확인 항목은 인계 전 확인하세요.");
  };
  $("#config-panel").hidden=false;
  refresh();
  setInterval(() => {
    if (mode === "live") { if (lastReceived && Date.now() - lastReceived > 10000) { stale=true; setConnection("데이터 수신 지연 · 마지막 관측 표시 · 시연 조치 잠금", "warning"); freezeCoils(); updateControls(); } refresh(); }
    else if (replay.playing) { replay.index = Math.min(replay.index + 1, replay.snapshots.length - 1); if (replay.index === replay.snapshots.length - 1) replay.playing = false; renderReplay(); }
  }, 1000);
})();
