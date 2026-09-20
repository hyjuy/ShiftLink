(() => {
  const labels = { running: "가동", paused: "일시정지", stopped: "정지", waiting: "대기", fault: "이상", recovering: "복구 관찰", warning: "주의", critical: "고장", normal: "정상", recovery: "복구 중", downstream_block: "하류 정체", upstream_drive_fault: "상류 구동 이상", hydraulic_supply_low: "유압 공급 저하", self_fault: "자체 이상", material_shortage: "소재 부족", planned_stop: "계획 정지" };
  const label = (value) => labels[value] || value || "—";
  const relationLabels = { material_flow: "소재 이송", utility_supply: "유틸리티 공급", hydraulic_supply: "유압 공급", pneumatic_supply: "공압 공급", power_supply: "전력 공급", mechanical_drive: "기계 구동", drive: "구동", interlock: "인터록", common_mode: "공통 영향", co_occurrence: "동시 발생 관계" };
  const escape = (value) => String(value ?? "—").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
  const stateClass = (item) => item.fault_level === "warning" ? "warning" : item.fault_level && item.fault_level !== "normal" ? "fault" : item.operating_state === "waiting" ? "waiting" : item.operating_state === "stopped" ? "stopped" : "normal";
  const statusText = (item) => [label(item.operating_state), label(item.fault_level), item.wait_reason && label(item.wait_reason)].filter(Boolean).join(" · ");
  const clock = (value) => value ? new Date(value).toLocaleString("ko-KR", { hour12: false }) : "—";
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
  if (typeof module !== "undefined") module.exports = { createHistory, acceptSnapshot, acceptEvents, connectionState, stateClass };
  if (typeof document === "undefined") return;
  const $ = (selector) => document.querySelector(selector);
  const setText = (selector, value) => { const el = $(selector); if (el) el.textContent = value; };
  let selectedId = null, lastSnapshot = null, mode = "live", lastReceived = 0, lastAdvance = 0;
  let history = createHistory(), requestEpoch = 0, loading = false, controlPending = false, applyPending = false;
  let liveConfig = createConfigCache(), replayConfig = createConfigCache();
  let replay = { snapshots: [], events: [], index: 0, playing: false, configId: null, configPreserved: true };
  const equipmentNodes = new Map();
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
  function renderEquipment(snapshot, config) {
    const route = config?.route || [];
    const equipment = [...(snapshot.equipment || [])].sort((a, b) => (route.includes(a.equipment_id) ? route.indexOf(a.equipment_id) : 100) - (route.includes(b.equipment_id) ? route.indexOf(b.equipment_id) : 100));
    const ids = new Set(equipment.map((item) => item.equipment_id));
    for (const [id, button] of equipmentNodes) if (!ids.has(id)) { button.remove(); equipmentNodes.delete(id); }
    for (const item of equipment) {
      let button = equipmentNodes.get(item.equipment_id);
      if (!button) {
        if (equipmentNodes.size === 0 || (route.length && equipmentNodes.size === route.length)) {
          const heading = document.createElement("p"); heading.className = "map-group-title";
          heading.textContent = equipmentNodes.size === 0 ? `소재 주경로 · ${route.map((id) => info(id, config).code || id).join(" → ")}` : "구동·공급·보조 설비";
          $("#line-map").append(heading);
        }
        button = document.createElement("button"); button.type = "button"; button.dataset.id = item.equipment_id;
        button.innerHTML = '<strong class="equipment-name"></strong><small class="equipment-code"></small><span class="equipment-state"></span><span class="coil-track"></span>';
        button.onclick = () => { selectedId = item.equipment_id; renderSnapshot(lastSnapshot, mode === "live" ? liveConfig.config : replayConfig.config); };
        equipmentNodes.set(item.equipment_id, button); $("#line-map").append(button);
      }
      button.className = `equipment ${route.includes(item.equipment_id) ? "material-equipment" : "utility-equipment"} ${stateClass(item)} ${selectedId === item.equipment_id ? "selected" : ""}`;
      button.setAttribute("aria-pressed", String(selectedId === item.equipment_id));
      button.querySelector(".equipment-name").textContent = name(item.equipment_id, config);
      button.querySelector(".equipment-code").textContent = `${info(item.equipment_id, config).code || ""} · ${item.equipment_id}`;
      button.querySelector(".equipment-state").textContent = statusText(item);
      const coils = (snapshot.coils || []).filter((coil) => coil.equipment_id === item.equipment_id);
      const track = button.querySelector(".coil-track"), coilIds = new Set(coils.map((coil) => coil.coil_id));
      for (const node of Array.from(track.children)) if (!coilIds.has(node.dataset.coil)) node.remove();
      for (const coil of coils) {
        let node = Array.from(track.children).find((child) => child.dataset.coil === coil.coil_id);
        if (!node) { node = document.createElement("span"); node.className = "coil"; node.dataset.coil = coil.coil_id; track.append(node); }
        node.title = `${coil.coil_id} · 위치 ${Math.round(Number(coil.position) * 100)}%`;
        node.setAttribute("role", "img"); node.setAttribute("aria-label", node.title);
        node.style.transition = mode === "live" && snapshot.line_mode === "running" ? "left 1s linear" : "none";
        node.style.left = `${Math.max(0, Math.min(1, Number(coil.position) || 0)) * 80}%`;
      }
      button.setAttribute("aria-label", `${name(item.equipment_id, config)} · ${statusText(item)} · 코일 ${coils.length}개`);
    }
    const relationships = (config?.relations || []).filter((r) => r.relation_type !== "material_flow");
    $("#utility-links").innerHTML = relationships.map((r) => `<p class="utility-link"><b>${escape(relationLabels[r.relation_type] || r.relation_type)}</b> ${escape(name(r.from_id, config))} → ${escape(name(r.to_id, config))}</p>`).join("") || "연결 정보 없음";
  }
  function renderDetail(snapshot, config) {
    const equipment = snapshot.equipment?.find((item) => item.equipment_id === selectedId);
    const measurements = (snapshot.measurements || []).filter((item) => item.equipment_id === selectedId);
    const configEq = config?.equipment?.find((e) => e.equipment_id === selectedId);
    if (!equipment) { $("#equipment-detail").innerHTML = "<h2>설비 상세</h2><p>설비 정보가 없습니다.</p>"; return; }
    const configInfo = config ? `<p class="config-ref">구성 <small>${config.version_label || config.config_id?.slice(0, 8)}</small></p>` : "";
    const assetInfo = configEq?.asset_id ? `<p>자산 ID: ${escape(configEq.asset_id)}</p>` : "";
    const profileInfo = configEq?.profile_id ? `<p>프로필: ${escape(configEq.profile_id)}</p>` : "";
    const signals = (configEq?.signals || []).map((spec) => {
      const m = measurements.find((m) => m.signal === spec.signal);
      return m ? `<li>${escape(spec.name || spec.signal)}: <strong>${escape(m.value)}</strong> ${escape(m.unit)} <small>품질 ${escape(m.quality)}</small></li>` : `<li>${escape(spec.name || spec.signal)}: <small>관측 없음</small></li>`;
    }).join("");
    $("#equipment-detail").innerHTML = `<h2>설비 상세</h2><p><b>${escape(name(selectedId, config))}</b> · ${escape(selectedId)}</p><p>${escape(statusText(equipment))}</p>${assetInfo}${profileInfo}${configInfo}<ul>${signals || "<li>신호 정의 없음</li>"}</ul>`;
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
    lastSnapshot = snapshot;
    if (!snapshot.equipment?.some((e) => e.equipment_id === selectedId)) selectedId = snapshot.equipment?.[0]?.equipment_id;
    setText("#line-mode", label(snapshot.line_mode)); setText("#sequence", snapshot.sequence);
    setText("#alarm-count", (snapshot.active_alarms || []).length); setText("#observed-at", clock(snapshot.simulated_at));
    setText("#run-id", snapshot.run_id); setText("#coil-count", (snapshot.coils || []).length);
    setText("#throughput", mode === "live" ? history.completed : replay.events.filter((e) => e.sequence <= snapshot.sequence && e.event_type === "coil_exited").length);
    const configBadge = config ? (replay.configPreserved === false ? "기록 재생 · 당시 구성 미보존" : "기록 재생 · 당시 구성") : "실시간 · 합성 데이터";
    setText("#mode-badge", mode === "live" ? "실시간 · 합성 데이터" : configBadge);
    if (mode === "live") $("#scenario").innerHTML = (config?.scenarios || []).map((s) => `<option value="${escape(s.scenario_id)}">${escape(s.scenario_id)}</option>`).join("");
    if (snapshot.scenario_id) $("#scenario").value = snapshot.scenario_id;
    if (snapshot.speed != null) $("#speed").value = String(snapshot.speed);
    renderEquipment(snapshot, config); renderDetail(snapshot, config);
    renderFeed("#alarm-list", snapshot.active_alarms || [], (a) => `${label(a.severity)} · ${name(a.equipment_id, config)} · ${a.code} · 발생 ${clock(a.raised_at)}`);
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
      lastReceived = Date.now(); renderSnapshot(snapshot, liveConfig.config);
      const stalled = snapshot.line_mode !== "paused" && Date.now() - lastAdvance > 10000;
      setConnection(stalled ? "운전 데이터 진행 지연" : connectionState(lastReceived, Date.now(), snapshot.line_mode), stalled ? "warning" : "");
    } catch (error) { if (epoch === requestEpoch && mode === "live") { setConnection(`연결 실패 · ${error.message}`, "fault"); freezeCoils(); } }
    finally { loading = false; }
  }
  function freezeCoils() { document.querySelectorAll(".coil").forEach((node) => { node.style.transition = "none"; }); }
  function updateControls() { document.querySelectorAll("#control-panel button, #control-panel select").forEach((el) => { el.disabled = mode !== "live" || controlPending; }); }
  async function control(command, extra = {}) {
    if (mode !== "live" || controlPending) return;
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
    lastSnapshot = null; equipmentNodes.clear(); $("#line-map").replaceChildren();
    for (const id of ["line-mode", "sequence", "alarm-count", "observed-at", "run-id", "coil-count", "throughput"]) setText(`#${id}`, "—");
    for (const id of ["equipment-detail", "sensor-trends", "alarm-list", "event-list"]) setText(`#${id}`, message);
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
  document.querySelectorAll("[data-command]").forEach((button) => { button.onclick = () => control(button.dataset.command); });
  $("#speed").onchange = (event) => control("speed", { speed: Number(event.target.value) });
  $("#scenario").onchange = (event) => control("scenario", { scenario_id: event.target.value });
  refresh();
  setInterval(() => {
    if (mode === "live") { if (lastReceived && Date.now() - lastReceived > 10000) { setConnection("데이터 수신 지연", "warning"); freezeCoils(); } refresh(); }
    else if (replay.playing) { replay.index = Math.min(replay.index + 1, replay.snapshots.length - 1); if (replay.index === replay.snapshots.length - 1) replay.playing = false; renderReplay(); }
  }, 1000);
})();
