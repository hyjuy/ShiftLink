(() => {
  const labels = { running: "가동", paused: "일시정지", stopped: "정지", waiting: "대기", fault: "이상", recovering: "복구 관찰", warning: "주의", critical: "고장", normal: "정상", recovery: "복구 중", downstream_block: "하류 정체", upstream_drive_fault: "상류 구동 이상", hydraulic_supply_low: "유압 공급 저하", self_fault: "자체 이상", material_shortage: "소재 부족", planned_stop: "계획 정지" };
  const label = (value) => labels[value] || value || "—";
  const relationLabels = { material_flow: "소재 이송", utility_supply: "유틸리티 공급", hydraulic_supply: "유압 공급", pneumatic_supply: "공압 공급", power_supply: "전력 공급", mechanical_drive: "기계 구동", drive: "구동", interlock: "인터록", common_mode: "공통 영향", co_occurrence: "동시 발생 관계" };
  const escape = (value) => String(value ?? "—").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
  const stateClass = (item) => item.fault_level === "warning" ? "warning" : item.fault_level && item.fault_level !== "normal" ? "fault" : item.operating_state === "waiting" ? "waiting" : item.operating_state === "stopped" ? "stopped" : "normal";
  const statusText = (item) => [label(item.operating_state), label(item.fault_level), item.wait_reason && label(item.wait_reason)].filter(Boolean).join(" · ");
  const clock = (value) => value ? new Date(value).toLocaleString("ko-KR", { hour12: false }) : "—";
  function createHistory() { return { runId: null, cursor: -1, events: [], snapshots: [], completed: 0 }; }
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
  let catalog = null, selectedId = null, lastSnapshot = null, mode = "live", lastReceived = 0, lastAdvance = 0;
  let history = createHistory(), requestEpoch = 0, loading = false, controlPending = false;
  let replay = { snapshots: [], events: [], index: 0, playing: false };
  const equipmentNodes = new Map();
  function setConnection(message, kind = "") { setText("#connection-status", message); $("#connection-status").className = `status-label ${kind}`; }
  async function request(url, options = {}) {
    const response = await fetch(url, { ...options, signal: AbortSignal.timeout(7000) });
    if (!response.ok) { const error = await response.json().catch(() => ({})); throw new Error(error.error || `요청 실패 (${response.status})`); }
    const data = await response.json();
    if (!data.is_synthetic) throw new Error("합성 데이터 표기가 없는 응답");
    return data;
  }
  const info = (id) => catalog?.equipment?.find((item) => item.equipment_id === id) || {};
  const name = (id) => info(id).name || info(id).code || id;
  function materialRoute() {
    const edges = (catalog?.relations || []).filter((r) => r.relation_type === "material_flow");
    const route = [], visited = new Set();
    let id = edges.find((r) => !edges.some((other) => other.to_id === r.from_id))?.from_id;
    while (id && !visited.has(id)) { route.push(id); visited.add(id); id = edges.filter((r) => r.from_id === id).sort((a, b) => (b.capacity?.value || 0) - (a.capacity?.value || 0))[0]?.to_id; }
    return route;
  }
  function renderEquipment(snapshot) {
    const route = materialRoute();
    const equipment = [...(snapshot.equipment || [])].sort((a, b) => (route.includes(a.equipment_id) ? route.indexOf(a.equipment_id) : 100) - (route.includes(b.equipment_id) ? route.indexOf(b.equipment_id) : 100));
    const ids = new Set(equipment.map((item) => item.equipment_id));
    for (const [id, button] of equipmentNodes) if (!ids.has(id)) { button.remove(); equipmentNodes.delete(id); }
    for (const item of equipment) {
      let button = equipmentNodes.get(item.equipment_id);
      if (!button) {
        if (equipmentNodes.size === 0 || (route.length && equipmentNodes.size === route.length)) {
          const heading = document.createElement("p"); heading.className = "map-group-title";
          heading.textContent = equipmentNodes.size === 0 ? `소재 주경로 · ${route.map((id) => info(id).code || id).join(" → ")}` : "구동·공급·보조 설비";
          $("#line-map").append(heading);
        }
        button = document.createElement("button"); button.type = "button"; button.dataset.id = item.equipment_id;
        button.innerHTML = '<strong class="equipment-name"></strong><small class="equipment-code"></small><span class="equipment-state"></span><span class="coil-track"></span>';
        button.onclick = () => { selectedId = item.equipment_id; renderSnapshot(lastSnapshot); };
        equipmentNodes.set(item.equipment_id, button); $("#line-map").append(button);
      }
      button.className = `equipment ${route.includes(item.equipment_id) ? "material-equipment" : "utility-equipment"} ${stateClass(item)} ${selectedId === item.equipment_id ? "selected" : ""}`;
      button.setAttribute("aria-pressed", String(selectedId === item.equipment_id));
      button.querySelector(".equipment-name").textContent = name(item.equipment_id);
      button.querySelector(".equipment-code").textContent = `${info(item.equipment_id).code || ""} · ${item.equipment_id}`;
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
      button.setAttribute("aria-label", `${name(item.equipment_id)} · ${statusText(item)} · 코일 ${coils.length}개`);
    }
    const relationships = (catalog?.relations || []).filter((r) => r.from_kind === "equipment" && r.to_kind === "equipment" && r.relation_type !== "material_flow");
    $("#utility-links").innerHTML = relationships.map((r) => `<p class="utility-link"><b>${escape(relationLabels[r.relation_type] || r.relation_type)}</b> ${escape(name(r.from_id))} → ${escape(name(r.to_id))}</p>`).join("") || "연결 정보 없음";
  }
  function renderDetail(snapshot) {
    const equipment = snapshot.equipment?.find((item) => item.equipment_id === selectedId);
    const measurements = (snapshot.measurements || []).filter((item) => item.equipment_id === selectedId), points = info(selectedId).measurement_points || [];
    $("#equipment-detail").innerHTML = equipment ? `<h2>설비 상세</h2><p><b>${escape(name(selectedId))}</b> · ${escape(selectedId)}</p><p>${escape(statusText(equipment))}</p><ul>${measurements.map((m) => `<li>${escape(points.find((p) => p.signal === m.signal)?.name || m.signal)}: <strong>${escape(m.value)}</strong> ${escape(m.unit)} <small>품질 ${escape(m.quality)}</small></li>`).join("") || "<li>측정값 없음</li>"}</ul>` : "<h2>설비 상세</h2><p>설비 정보가 없습니다.</p>";
    const select = $("#signal-select"), signature = measurements.map((m) => m.signal).join("|");
    if (select.dataset.signals !== signature) {
      select.innerHTML = measurements.map((m) => `<option value="${escape(m.signal)}">${escape(points.find((p) => p.signal === m.signal)?.name || m.signal)} (${escape(m.unit)})</option>`).join("");
      select.dataset.signals = signature;
    }
    renderTrend();
  }
  function renderTrend() {
    const signal = $("#signal-select").value;
    const snapshots = mode === "live" ? history.snapshots : replay.snapshots.slice(Math.max(0, replay.index - 179), replay.index + 1);
    const values = snapshots.map((s) => ({ time: s.simulated_at, measurement: s.measurements?.find((m) => m.equipment_id === selectedId && m.signal === signal) })).filter((p) => Number.isFinite(p.measurement?.value));
    if (!values.length) { $("#sensor-trends").textContent = "추이 데이터 없음"; setText("#trend-description", "설비와 신호를 선택하세요."); return; }
    const numbers = values.map((p) => p.measurement.value), min = Math.min(...numbers), max = Math.max(...numbers), spread = max - min || 1;
    const coordinates = numbers.map((v, i) => `${35 + i / Math.max(1, numbers.length - 1) * 370},${120 - (v - min) / spread * 90}`).join(" ");
    const description = `${signal} · ${values.length}개 관측 · 최소 ${min} / 최대 ${max} ${values[0].measurement.unit} · ${clock(values[0].time)} ~ ${clock(values.at(-1).time)}`;
    $("#sensor-trends").innerHTML = `<svg viewBox="0 0 420 150" role="img" aria-label="${escape(description)}"><title>${escape(description)}</title><path d="M35 15 V125 H410" fill="none" stroke="currentColor" opacity=".4"/><polyline points="${coordinates}" fill="none" stroke="#53dfc6" stroke-width="3"/><text x="3" y="20" fill="currentColor" font-size="10">${max}</text><text x="3" y="123" fill="currentColor" font-size="10">${min}</text></svg>`;
    setText("#trend-description", description);
  }
  function renderFeed(selector, items, format) { $(selector).innerHTML = items.length ? items.map((item) => `<li class="${item.severity === "critical" ? "fault" : ""}">${escape(format(item))}</li>`).join("") : "<li>없음</li>"; }
  function renderSnapshot(snapshot) {
    if (!snapshot) return;
    lastSnapshot = snapshot;
    if (!snapshot.equipment?.some((e) => e.equipment_id === selectedId)) selectedId = snapshot.equipment?.[0]?.equipment_id;
    setText("#line-mode", label(snapshot.line_mode)); setText("#sequence", snapshot.sequence);
    setText("#alarm-count", (snapshot.active_alarms || []).length); setText("#observed-at", clock(snapshot.simulated_at));
    setText("#run-id", snapshot.run_id); setText("#coil-count", (snapshot.coils || []).length);
    setText("#throughput", mode === "live" ? history.completed : replay.events.filter((e) => e.sequence <= snapshot.sequence && e.event_type === "coil_exited").length);
    setText("#mode-badge", mode === "live" ? "실시간 · 합성 데이터" : "기록 재생 · 합성 데이터");
    $("#scenario").value = snapshot.scenario_id;
    if (snapshot.speed != null) $("#speed").value = String(snapshot.speed);
    renderEquipment(snapshot); renderDetail(snapshot);
    renderFeed("#alarm-list", snapshot.active_alarms || [], (a) => `${label(a.severity)} · ${name(a.equipment_id)} · ${a.code} · 발생 ${clock(a.raised_at)}`);
    const events = mode === "live" ? history.events : replay.events.filter((e) => e.sequence <= snapshot.sequence);
    renderFeed("#event-list", events.slice(-25).reverse(), (e) => `${clock(e.occurred_at)} · ${e.event_type} · ${e.observation}`);
    for (const format of ["jsonl", "csv"]) { const link = $(`#export-${format}`); link.href = `/api/export?run_id=${encodeURIComponent(snapshot.run_id)}&format=${format}`; link.download = `${snapshot.run_id}.${format}`; }
  }
  async function refresh() {
    if (mode !== "live" || loading) return;
    loading = true; const epoch = requestEpoch;
    try {
      if (!catalog) catalog = (await request("/api/catalog")).data;
      const snapshot = await request("/api/state");
      if (epoch !== requestEpoch || mode !== "live") return;
      const previous = history.snapshots.at(-1);
      if (!previous || previous.run_id !== snapshot.run_id || previous.sequence !== snapshot.sequence || snapshot.line_mode === "paused") lastAdvance = Date.now();
      acceptSnapshot(history, snapshot);
      // Re-read the boundary tick: controls may add another event at that tick.
      const payload = await request(`/api/events?after_sequence=${Math.max(-1, history.cursor - 1)}`);
      if (epoch !== requestEpoch || mode !== "live") return;
      payload.events = (payload.events || []).filter((event) => event.sequence <= snapshot.sequence);
      if (!acceptEvents(history, payload)) { setConnection("새 실행 동기화 중"); return; }
      lastReceived = Date.now(); renderSnapshot(snapshot);
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
      replay = { snapshots: payload.snapshots || [], events: payload.events || [], index: 0, playing: false };
      $("#replay-sequence").max = String(Math.max(0, replay.snapshots.length - 1)); renderReplay();
    } catch (error) { if (epoch === requestEpoch) setConnection(`재생 조회 실패 · ${error.message}`, "fault"); }
  }
  function renderReplay() {
    $("#replay-play").textContent = replay.playing ? "재생 일시정지" : "기록 재생";
    $("#replay-sequence").value = String(replay.index); $("#replay-play").disabled = !replay.snapshots.length;
    if (!replay.snapshots.length) { clearDisplay("저장된 스냅샷이 없습니다."); setText("#replay-position", "저장된 스냅샷이 없습니다."); setConnection("재생할 기록 없음", "warning"); return; }
    renderSnapshot(replay.snapshots[replay.index]); setText("#replay-position", `${replay.index + 1} / ${replay.snapshots.length} · 순번 ${lastSnapshot.sequence}`);
    setConnection(replay.playing ? "기록 재생 중 · 실시간 제어 분리" : "기록 재생 일시정지 · 실시간 제어 분리");
  }
  function clearDisplay(message) {
    lastSnapshot = null; equipmentNodes.clear(); $("#line-map").replaceChildren();
    for (const id of ["line-mode", "sequence", "alarm-count", "observed-at", "run-id", "coil-count", "throughput"]) setText(`#${id}`, "—");
    for (const id of ["equipment-detail", "sensor-trends", "alarm-list", "event-list"]) setText(`#${id}`, message);
    for (const format of ["jsonl", "csv"]) $(`#export-${format}`).removeAttribute("href");
    setText("#mode-badge", mode === "live" ? "실시간 · 합성 데이터" : "기록 재생 · 합성 데이터");
  }
  $("#view-mode").onchange = async (event) => {
    mode = event.target.value; requestEpoch++; replay.playing = false; freezeCoils(); clearDisplay("데이터 불러오는 중");
    $("#replay-controls").hidden = mode !== "replay"; updateControls();
    try { if (mode === "replay") { await loadRuns(); await loadReplay(); } else { history = createHistory(); await refresh(); } }
    catch (error) { setConnection(`조회 실패 · ${error.message}`, "fault"); }
  };
  $("#replay-run").onchange = loadReplay;
  $("#replay-refresh").onclick = async () => { try { await loadRuns(); await loadReplay(); } catch (error) { setConnection(error.message, "fault"); } };
  $("#replay-play").onclick = () => { if (replay.index >= replay.snapshots.length - 1) replay.index = 0; replay.playing = !replay.playing; renderReplay(); };
  $("#replay-sequence").oninput = (event) => { replay.index = Number(event.target.value); replay.playing = false; renderReplay(); };
  $("#signal-select").onchange = renderTrend;
  document.querySelectorAll("[data-command]").forEach((button) => { button.onclick = () => control(button.dataset.command); });
  $("#speed").onchange = (event) => control("speed", { speed: Number(event.target.value) });
  $("#scenario").onchange = (event) => control("scenario", { scenario_id: event.target.value });
  refresh();
  setInterval(() => {
    if (mode === "live") { if (lastReceived && Date.now() - lastReceived > 10000) { setConnection("데이터 수신 지연", "warning"); freezeCoils(); } refresh(); }
    else if (replay.playing) { replay.index = Math.min(replay.index + 1, replay.snapshots.length - 1); if (replay.index === replay.snapshots.length - 1) replay.playing = false; renderReplay(); }
  }, 1000);
})();
