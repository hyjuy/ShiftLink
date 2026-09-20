/* Pure observation-to-view mapping. No plant control or inferred fault diagnosis. */
(() => {
  const esc = value => String(value ?? "—").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
  const types = {material_flow:"소재 이송",drive:"구동 전달",hydraulic_supply:"유압 공급",power_supply:"전력 공급",pneumatic_supply:"공압 공급",interlock:"인터록",common_mode:"공통 영향",co_occurrence:"동시 발생 관계"};
  const roles = {rt:["롤러 이송대","코일을 받쳐 다음 설비로 옮깁니다."], cv:["컨베이어","코일을 출측으로 운반합니다."], gr:["감속기·모터","연결된 롤러에 회전력을 전달합니다."],hpu:["유압장치","클램프·승강 장치에 유압을 공급합니다."],pdp:["배전반","연결 설비에 전력을 공급합니다."],cau:["공압장치","연결 설비에 압축 공기를 공급합니다."]};
  const states = {running:"가동",stopped:"정지",waiting:"대기",normal:"정상",warning:"주의",critical:"자체 이상"};
  const partNames = {cooling:"냉각 계통",seal:"씰",bearing:"베어링",oil:"유압유 상태",belt:"이송 벨트"};
  const stamp = value => value ? new Date(value).toLocaleTimeString("ko-KR",{hour12:false}) : "시각 없음";
  const title = eq => eq?.code || eq?.equipment_id || "관측 없음";

  function buildOperatorModel(snapshot, config, selectedId, partId = null) {
    const route = config?.route || [], relations = [...(config?.relations || []), ...(config?.branches || [])];
    const materialIds = new Set(relations.filter(r=>r.relation_type === "material_flow").flatMap(r=>[r.from_id,r.to_id]));
    const nodes = (snapshot.equipment || []).map(state => {
      const eq = config?.equipment?.find(e=>e.equipment_id===state.equipment_id) || {};
      return {...eq, ...state, group: route.includes(state.equipment_id) ? "route" : materialIds.has(state.equipment_id) ? "branch" : "support", role:roles[eq.profile_id] || ["설비","구성에 등록된 역할을 확인하세요."], coils:(snapshot.coils || []).filter(c=>c.equipment_id===state.equipment_id)};
    });
    // Unknown profiles must not invent machinery internals.
    for (const n of nodes) if (!roles[n.profile_id]) n.role = ["설비", "구성에 등록된 역할을 확인하세요."];
    const lookup = id => nodes.find(n=>n.equipment_id===id);
    const faults = nodes.filter(n=>n.fault_level && n.fault_level!=="normal");
    const spec = config?.scenarios?.find(s=>s.scenario_id===snapshot.scenario_id);
    const cause = nodes.find(n=>n.active!==false && (n.capabilities || []).includes(spec?.cause_capability));
    const selected = lookup(selectedId) || faults[0] || nodes[0];
    const links = relations.filter(r=>lookup(r.from_id) && lookup(r.to_id)).map(r=>{
      const from = lookup(r.from_id), to = lookup(r.to_id);
      const affected = Boolean(spec && from.equipment_id===cause?.equipment_id && faults.includes(from) &&
        r.relation_type===spec.propagation_relation && to.operating_state==="waiting" && to.wait_reason===spec.wait_reason);
      return {...r, from, to, affected, label:types[r.relation_type] || r.relation_type};
    });
    const problemPart = selected?.equipment_id===cause?.equipment_id && snapshot.scenario_id!=="normal" ? spec?.component_id || null : null;
    const parts = (snapshot.components || []).filter(c=>c.equipment_id===selected?.equipment_id);
    const selectedPart = parts.find(p=>p.component_id===partId) || parts.find(p=>p.component_id===problemPart) || null;
    const measurements = (selected?.signals || []).map(signal=>{
      const m = (snapshot.measurements || []).find(m=>m.equipment_id===selected.equipment_id && m.signal===signal.signal);
      const age = m ? (Date.parse(snapshot.simulated_at)-Date.parse(m.observed_at))/1000 : NaN;
      const known = Boolean(m && Number.isFinite(m.value));
      const trustworthy = known && m.quality==="good" && Number.isFinite(age) && age>=0 && age<=10;
      const hasRange = signal.normal_min!=null || signal.normal_max!=null;
      const inRange = hasRange && trustworthy && (signal.normal_min==null || m.value>=signal.normal_min) && (signal.normal_max==null || m.value<=signal.normal_max);
      return {...signal, observation:m, known, trustworthy, hasRange, inRange,
        relevant:(spec?.signal_effects || []).some(e=>e.signal===signal.signal && (selected.capabilities || []).includes(e.capability))};
    }).sort((a,b)=>Number(b.relevant)-Number(a.relevant));
    return {snapshot, config, nodes, links, faults, selected, cause, spec, problemPart, selectedPart, parts, measurements,
      held:(snapshot.coils || []).filter(c=>c.quality_status==="hold"), lookup};
  }

  function machineSvg(kind) {
    const roller = (x) => `<g class="rotor" style="transform-origin:${x}px 66px"><circle cx="${x}" cy="66" r="9"/><path d="M${x - 6} 66h12M${x} 60v12"/></g>`;
    const drawings = {
      rt: `<path d="M17 78h146M30 78v18M150 78v18"/>${[32, 61, 90, 119, 148].map(roller).join("")}<path d="M18 51v-8h15M162 51v-8h-15"/>`,
      cv: `<rect x="17" y="53" width="146" height="27" rx="13"/><path class="belt-motion" d="M30 55h120M30 78h120"/>${[32, 148].map(roller).join("")}<path d="M40 81v15M140 81v15"/>`,
      gr: `<rect x="15" y="48" width="55" height="36" rx="8"/><path d="M25 54v24M35 54v24M45 54v24M70 66h15M129 66h35"/><g class="rotor" style="transform-origin:106px 66px"><circle cx="106" cy="66" r="23"/><circle cx="106" cy="66" r="8"/><path d="M106 39v17M106 76v17M79 66h17M116 66h17M87 47l12 12M113 73l12 12M87 85l12-12M113 59l12-12"/></g><path d="M20 91h120"/>`,
      hpu: `<rect x="25" y="48" width="106" height="43" rx="5"/><path class="fluid" d="M29 72h98v15H29z"/><circle cx="60" cy="32" r="14"/><path d="M60 46v13M60 32l8-7M131 68h24V31h16"/><path class="supply-motion" d="M132 68h23V31h16"/>`,
      pdp: `<rect x="44" y="15" width="92" height="78" rx="6"/><path d="M90 20v68M113 52v12"/><circle cx="59" cy="30" r="3"/><circle cx="73" cy="30" r="3"/><path class="power-symbol" d="M73 43L60 64h13l-7 16 18-24H71z"/>`,
      cau: `<rect x="25" y="44" width="115" height="40" rx="20"/><path d="M45 84v11M119 84v11M140 64h20V32h13M78 44V31"/><circle cx="78" cy="24" r="10"/><path d="M78 24l5-5"/><path class="supply-motion" d="M35 65h125V32h13"/>`,
      generic: `<rect x="40" y="28" width="100" height="60" rx="8"/><circle cx="90" cy="58" r="16"/><path d="M90 48v20M80 58h20"/>`
    };
    return `<svg class="machine-illustration" x="-85" y="22" width="170" height="99" viewBox="0 0 180 105" aria-hidden="true" focusable="false">${drawings[kind] || drawings.generic}</svg>`;
  }
  function layout(model) {
    let row=0; const placed=[];
    const groups = [model.nodes.filter(n=>n.group==="route").sort((a,b)=>model.config.route.indexOf(a.equipment_id)-model.config.route.indexOf(b.equipment_id)),
      model.nodes.filter(n=>n.group==="branch" || (n.capabilities || []).includes("drive")),
      model.nodes.filter(n=>n.group==="support" && !(n.capabilities || []).includes("drive"))];
    for (const group of groups) {
      const cols=Math.min(4,group.length);
      group.forEach((n,i)=>placed.push({...n,x:(i%cols+0.5)*960/cols,y:62+(row+Math.floor(i/cols))*235}));
      row+=Math.ceil(group.length/4);
    }
    return {nodes:placed,height:Math.max(180,row*235+8)};
  }

  const relationKey = l => `${l.from_id}|${l.to_id}|${l.relation_type}`;
  function flowView(model, experience="learn", filter="related", selectedRelation="") {
    if (!model.nodes.length) return '<p class="empty-state">설비 관측 없음</p>';
    const map=layout(model), activeId=model.selected?.equipment_id;
    const links=model.links.filter(l=>filter==="all" || l.relation_type==="material_flow" || (filter!=="material" && l.affected) || (filter==="related" && [l.from_id,l.to_id].includes(activeId)));
    const edges=links.map((l,i)=>{
      const a=map.nodes.find(n=>n.equipment_id===l.from_id), b=map.nodes.find(n=>n.equipment_id===l.to_id);
      const lateral=a.y===b.y, sx=a.x+(lateral ? Math.sign(b.x-a.x)*91 : 0), sy=a.y+(lateral ? 65 : b.y>a.y ? 146 : -48), ex=b.x-(lateral ? Math.sign(b.x-a.x)*96 : 0), ey=b.y+(lateral ? 65 : b.y>a.y ? -52 : 150);
      const material=l.relation_type==="material_flow", cls=l.affected?"affected":material?"material":"related";
      const d=lateral ? (l.relation_type==="interlock" ? `M${sx} ${sy+20} Q${(sx+ex)/2} ${sy+85} ${ex} ${ey+20}` : `M${sx} ${sy} L${ex} ${ey}`) : `M${sx} ${sy} C${sx} ${(sy+ey)/2},${ex} ${(sy+ey)/2},${ex} ${ey}`;
      const description=`${title(a)} → ${title(b)} · ${l.label} · ${l.affected?"관측된 영향 대기":"구성상 관계 · 원인 확정 아님"}`;
      return `<g class="flow-edge ${cls} ${selectedRelation===relationKey(l)?"selected":""}" role="button" tabindex="0" data-equipment="${esc(l.from_id)}" data-relation="${esc(relationKey(l))}" aria-pressed="${selectedRelation===relationKey(l)}" aria-label="${esc(description)}"><title>${esc(description)}</title><path class="edge-hit" d="${d}"/><path class="edge-line" d="${d}" marker-end="url(#arrow-${cls})"/>${!material?`<text class="edge-label" x="${(sx+ex)/2+6}" y="${(sy+ey)/2-7}">${esc(l.label)}</text>`:""}</g>`;
    }).join("");
    const nodes=map.nodes.map(n=>{
      const fault=n.fault_level!=="normal", held=n.coils.some(c=>c.quality_status==="hold"), waiting=n.operating_state==="waiting";
      const waitLabel=model.links.some(l=>l.affected && l.to_id===n.equipment_id)?"영향 대기":({recovery:"복구 관찰",material_shortage:"소재 대기",planned_stop:"계획 대기"}[n.wait_reason] || "일반 대기");
      const state=fault?(n.fault_level==="warning"?"주의 관측":"자체 이상"):held?"제품 보류":waiting?waitLabel:states[n.operating_state] || n.operating_state;
      const cls=fault?"fault":held?"held":waiting?"waiting":"normal";
      const group=n.group==="route"?`${model.config.route.indexOf(n.equipment_id)+1} · 소재 본선`:n.group==="branch"?"물류 분기 · 시연 제외":"구동·공급";
      const component=n.equipment_id===model.cause?.equipment_id && model.spec?.component_id ? `${partNames[model.spec.component_id] || model.spec.component_id} · 가정` : "";
      const description=`${title(n)} · ${n.role[0]} · ${state} · ${group}${component?` · ${component}`:""}`;
      const dots=n.coils.map(c=>`<circle class="flow-coil ${c.quality_status==="hold"?"held":""}" data-coil="${esc(c.coil_id)}" cx="-60" cy="65" r="11"><title>${esc(c.coil_id)}${c.quality_status==="hold"?" · 제품 보류":""}</title></circle>`).join("");
      return `<g transform="translate(${n.x} ${n.y})" class="flow-node ${cls} ${activeId===n.equipment_id?"selected":""}" role="button" tabindex="0" data-equipment="${esc(n.equipment_id)}" aria-pressed="${activeId===n.equipment_id}" aria-label="${esc(description)}"><title>${esc(description)}</title><rect class="node-body" x="-91" y="-46" width="182" height="192" rx="10"/><text class="node-code" x="-78" y="-23">${esc(title(n))}</text><text class="node-status" x="-78" y="-3">${fault?"! ":held?"Ⅱ ":waiting?"↳ ":""}${esc(state)}</text><text class="node-role" x="-78" y="17">${esc(n.role[0])}</text><text class="node-meta" x="-78" y="135">${esc(component || group)}</text>${machineSvg(n.profile_id)}${dots}</g>`;
    }).join("");
    return `${!model.config?'<p class="hint">구성 미보존 · 연결·역할을 추정하지 않습니다.</p>':""}<svg class="flow-map" viewBox="0 0 960 ${map.height}" role="group" aria-label="설비 관계도 · Tab으로 설비와 연결을 이동하고 Enter로 선택"><defs>${["material","related","affected"].map(c=>`<marker id="arrow-${c}" class="arrow-${c}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z"/></marker>`).join("")}</defs>${edges}${nodes}</svg>${experience==="learn"?'<p class="learn-note">① 본선 화살표는 코일 이동 순서입니다. ② 구동·공급 설비를 누르면 연결 대상이 보입니다. ③ 점선은 공급·인터록, 굵은 주황선은 서버가 관측한 영향 대기입니다. 배치는 위치 개념도이며 실제 거리·부품 배치가 아닙니다.</p>':""}`;
  }

  function incidentView(model) {
    const items=model.faults.map(n=>{
      const part=n.equipment_id===model.cause?.equipment_id && model.spec?.component_id;
      const affected=model.links.filter(l=>l.affected && l.from_id===n.equipment_id).map(l=>title(l.to));
      return `<button type="button" data-equipment="${esc(n.equipment_id)}" class="incident-item fault"><span class="incident-kind">! ${n.fault_level==="warning"?"주의":"자체 이상"}</span><b>${esc(title(n))} · ${esc(n.role[0])}</b><span>${part?`${esc(partNames[part] || part)} · 시연 가정`:"문제 부품 미확정 · 근거 확인"}</span><small>영향 대기 ${affected.length}대${affected.length?` · ${esc(affected.join(", "))}`:""}</small></button>`;
    });
    if (model.held.length) items.push(`<button type="button" class="incident-item held" data-equipment="${esc(model.held[0].equipment_id)}"><span class="incident-kind">Ⅱ 제품 검사·보류</span><b>영향 코일 ${model.held.length}개</b><span>설비 고장과 별개 · 해제 전 이송 차단</span><small>${model.held.map(c=>esc(c.coil_id)).join(" · ")}</small></button>`);
    return items.join("") || `<p class="no-incident">${model.snapshot.recovery?.stage==="stabilizing"?"복구 관찰 중 · 아직 정상 복귀 전입니다.":"현재 자체 이상·제품 보류 없음"} <span>서버 관측 기준 · 운전 상태와 측정값을 함께 확인하세요.</span></p>`;
  }

  function evidenceView(model, selectedRelation="") {
    const eq=model.selected;
    if (!eq) return "<p>설비를 선택하세요.</p>";
    const incoming=model.links.filter(l=>l.to_id===eq.equipment_id && l.affected);
    const related=model.links.filter(l=>l.from_id===eq.equipment_id || l.to_id===eq.equipment_id);
    const relation=model.links.find(l=>relationKey(l)===selectedRelation);
    const relationNote=relation?`<p class="selected-relation"><b>선택 연결: ${esc(title(relation.from))} → ${esc(title(relation.to))}</b><br>${esc(relation.label)} · ${relation.affected?"관측된 영향 대기":"구성상 연결 · 영향 또는 원인 확정 아님"}</p>`:"";
    const measurements=model.measurements.map(s=>{
      const band=s.normal_min==null&&s.normal_max==null?"기준 없음":`${s.normal_min??"하한 없음"} ~ ${s.normal_max??"상한 없음"}`;
      const finding=!s.known?"관측 없음":!s.trustworthy?"품질·시각 확인 필요":!s.hasRange?"기준 없음 · 판정 불가":s.inRange?"구성 범위 내":"구성 범위 이탈 · 확인 필요";
      return `<tr class="${s.relevant?"relevant":""}"><th scope="row">${esc(s.name || s.signal)}<small>${esc(s.signal)}</small></th><td><b>${s.known?esc(s.observation.value):"—"}</b> ${esc(s.unit)}<small>${esc(finding)}</small></td><td>${esc(band)} ${esc(s.unit)}<small>${s.observation?`${esc(s.observation.quality)} · ${esc(stamp(s.observation.observed_at))}`:"기록 없음"}</small></td></tr>`;
    }).join("");
    return `${relationNote}<p class="location-path">라인 ${esc(model.snapshot.line_id)} / ${esc(eq.segment_id || "구간 미등록")} / <b>${esc(title(eq))}</b>${model.selectedPart?` / ${esc(model.selectedPart.name)}`:""}</p><p>${esc(eq.role[1])}</p>${incoming.length?`<p class="impact-explanation">${incoming.map(l=>`${esc(title(l.from))}의 ${esc(l.label)}`).join(", ")} 영향으로 대기합니다. 이 설비의 자체 고장을 뜻하지 않습니다.</p>`:""}<div class="evidence-scroll"><table class="evidence-table"><caption>관측 근거 · 정상 범위는 시연 구성값이며 안전 재가동 기준이 아닙니다.</caption><thead><tr><th>측정 항목</th><th>현재 관측</th><th>정상 범위 / 품질·시각</th></tr></thead><tbody>${measurements || '<tr><td colspan="3">관측 신호 정의 없음</td></tr>'}</tbody></table></div><details class="related-detail"><summary>연결 근거 ${related.length}개 · 구성상 관계는 원인 확정이 아닙니다</summary><ul>${related.map(l=>`<li>${l.affected?"<b>영향 대기</b> · ":""}<button type="button" data-equipment="${esc(l.from_id)}">${esc(title(l.from))}</button> → <button type="button" data-equipment="${esc(l.to_id)}">${esc(title(l.to))}</button> · ${esc(l.label)}</li>`).join("") || "<li>연결 정보 없음</li>"}</ul></details>`;
  }

  function partView(model) {
    if (!model.parts.length) return '<p class="hint">부품 상태 기록 없음 · 부품을 임의로 추정하지 않습니다.</p>';
    const chosen=model.selectedPart;
    const part=model.problemPart;
    return `<p class="part-caption">${part?`시연에서 가정한 문제 부품: <b>${esc(partNames[part] || part)}</b> · 센서만으로 확정한 진단이 아닙니다.`:"문제 부품 미확정 · 아래는 구성된 모의 부품입니다."}</p><div class="part-locator" role="group" aria-label="부품 위치 개념도 · 실제 조립 위치 아님">${model.parts.map(p=>`<button type="button" data-part="${esc(p.component_id)}" aria-pressed="${chosen?.component_id===p.component_id}" class="part-target ${p.component_id===part?"suspect":""}"><span aria-hidden="true">${p.component_id===part?"!":"◇"}</span><b>${esc(p.name)}</b><small>${p.component_id===part?"시연 가정 부품":"모의 구성 부품"}</small></button>`).join("")}</div>${chosen?`<p class="part-context"><b>${esc(chosen.name)}</b> · 모의 건전도 ${Number(chosen.health_percent).toFixed(1)}% · 운전 ${(chosen.operating_seconds/3600).toFixed(3)} h · 정비 ${Number(chosen.maintenance_count)}회</p>`:""}<p class="hint">위치는 기능별 개념 배치입니다. 실제 잔여수명·고장 확률을 뜻하지 않습니다.</p>`;
  }

  const api={buildOperatorModel,flowView,incidentView,evidenceView,partView,layout,relationKey};
  if (typeof module!=="undefined") module.exports=api;
  if (typeof window!=="undefined") window.MesOperator=api;
})();
