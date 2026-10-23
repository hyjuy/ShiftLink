(() => {
  'use strict';
  const $=id=>document.getElementById(id),key='shiftlink.mes.adminToken';
  const labels={pending_review:'검토 대기',changes_requested:'보완 요청',review_approved:'검토 승인',quality_passed:'검수 통과',rejected:'반려'};
  const publicationStates={embedding_pending:'임베딩 대기',embedding_running:'임베딩 처리 중',embedding_failed:'임베딩 실패',published:'검색 반영 완료',superseded:'재검토로 검색 제외'};
  const types={T1:'징후 해석',T2:'운전 조건',T3:'문제 해결',T4:'인계 해결 사례',T5:'안전 조치',T6:'재가동 경험'};
  const outcomes={open:'미해결',temporary:'임시 복구',failed:'실패',resolved:'해결'};
  const normalStates={unconfirmed:'미확인',observing:'관찰 중',no_recurrence:'관찰 종료·재발 없음',recurred:'관찰 중 재발'};
  const observationFields=[['interpretation','징후 해석'],['interpretation_basis','해석 근거'],
    ['condition_signal','운전 조건 항목'],['condition_op','비교 방식'],['condition_value','운전 조건 값'],
    ['condition_unit','운전 조건 단위'],['condition_method','조건에서 수행한 방법'],['condition_result','조건에서 관찰한 결과'],
    ['safety_notes','발견한 위험·주의사항'],['safety_action','중지·격리 조치'],['safety_basis','안전 근거']];
  let token='',drafts=[],selected=null,detail=null,detailRequest=0,listRequest=0,saving=false;
  try{token=sessionStorage.getItem(key)||'';}catch(_){}
  const el=(tag,className,text)=>{const node=document.createElement(tag);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node;};
  const stamp=value=>value&&Number.isFinite(Date.parse(value))?(/[zZ]|[+-]\d\d:\d\d$/.test(value)?new Date(value).toLocaleString('sv-SE',{timeZone:'Asia/Seoul'}).slice(0,16):value.replace('T',' ').slice(0,16)):'미기재';
  const status=value=>labels[value]||'상태 확인';
  function message(text,error=false){$('review-message').textContent=text;$('review-message').classList.toggle('is-error',error);}
  function session(value){
    token=value;try{if(token)sessionStorage.setItem(key,token);else sessionStorage.removeItem(key);}catch(_){}
    $('review-login').hidden=!!token;$('review-workspace').hidden=!token;$('review-refresh').hidden=!token;$('review-logout').hidden=!token;
    if(!token){drafts=[];detail=null;selected=null;detailRequest++;listRequest++;$('candidate-list').replaceChildren();$('candidate-detail').replaceChildren();}
  }
  async function request(path,body){
    const headers={};if(token)headers.Authorization='Bearer '+token;if(body!==undefined)headers['Content-Type']='application/json';
    const response=await fetch(path,{method:body===undefined?'GET':'POST',headers,body:body===undefined?undefined:JSON.stringify(body),cache:'no-store',signal:AbortSignal.timeout(15000)});
    const data=await response.json();
    if(!response.ok){if(response.status===401)session('');const error=new Error(data.error||'요청을 처리하지 못했습니다.');error.status=response.status;throw error;}
    return data;
  }
  function errorText(error){return error.name==='TypeError'||error.name==='TimeoutError'?'서버에 연결하지 못했습니다. 다시 시도해 주세요.':error.message;}
  function badge(value){return el('span','review-badge '+({review_approved:'approved',changes_requested:'changes',rejected:'rejected'}[value]||''),status(value));}
  function filtered(){
    const search=$('candidate-search').value.trim().toLowerCase(),state=$('candidate-status').value,type=$('candidate-type').value;
    return drafts.filter(item=>(state==='all'||item.status===state)&&(type==='all'||item.card.tacit_type===type)&&
      (!search||[item.draft_id,item.card.title,item.card.equipment,item.card.component,item.card.mes_equipment_id].join(' ').toLowerCase().includes(search)));
  }
  function renderList(){
    const items=filtered(),box=$('candidate-list');box.replaceChildren();$('candidate-count').textContent=items.length+'건';
    if(!items.length){box.append(el('p','review-empty',drafts.length?'조건에 맞는 후보가 없습니다.':'아직 등록된 지식카드 후보가 없습니다.'));return;}
    for(const item of items){
      const button=el('button');button.type='button';button.dataset.draftId=item.draft_id;button.setAttribute('aria-pressed',String(item.draft_id===selected));
      const labels=el('span','candidate-labels');labels.append(el('span','candidate-id',item.draft_id),badge(item.status));
      button.append(labels,el('span','candidate-title',item.card.title),
        el('span','candidate-meta',[item.card.tacit_type,types[item.card.tacit_type]||'',item.card.component||item.card.equipment].filter(Boolean).join(' · ')),el('span','candidate-meta','등록 '+stamp(item.created_at)));
      button.addEventListener('click',()=>{if(!saving)loadDetail(item.draft_id,true);});box.append(button);
    }
  }
  function facts(pairs){const dl=el('dl','review-facts');for(const [label,value] of pairs)dl.append(el('dt','',label),el('dd','',value===null||value===undefined||value===''?'미기재':String(value)));return dl;}
  function section(title){const box=el('section','candidate-section');box.append(el('h3','',title));return box;}
  function disclosure(title){const node=el('details');node.append(el('summary','',title));return node;}
  function renderSteps(record){
    const box=el('div');
    for(const step of (record.action_steps||[]).filter(step=>step.action||step.observed_result)){
      const row=el('div','review-step'),dl=el('dl');row.append(el('p','step-person',(step.worker||'근무자 미기재')+' · '+stamp(step.performed_at)));
      dl.append(el('dt','','조치 내용'),el('dd','',step.action||'미기재'),el('dt','','조치 결과'),el('dd','',step.observed_result||'미확인'));row.append(dl);box.append(row);
    }
    if(!box.children.length)box.append(el('p','',record.solution||'별도 조치 기록 없음'),el('p','',record.result||''));
    return box;
  }
  function timeline(draft){
    if(draft.review_flags.handover_chain?.length)return draft.review_flags.handover_chain;
    const ref=draft.review_flags.work_report||{};
    return (draft.sources||[]).flatMap(source=>(source.work_report?.records||[]).flatMap((record,index)=>
      source.handover_id===ref.handover_id&&ref.record_index!==undefined&&index!==ref.record_index?[]:[{record,record_index:index,handover_id:source.handover_id,required_context:source.required_context||{},created_at:source.created_at}]));
  }
  function renderDetail(draft){
    detail=draft;const box=$('candidate-detail');box.replaceChildren();
    const head=el('header','detail-heading'),labels=el('div','candidate-labels');
    labels.append(el('span','candidate-id',draft.draft_id),el('span','candidate-type',draft.card.tacit_type),badge(draft.status));
    head.append(labels,el('h2','',draft.card.title),
      el('p','',(types[draft.card.tacit_type]||draft.card.tacit_type)+' · '+draft.card.component),el('p','','후보 등록 '+stamp(draft.created_at)));box.append(head);
    const flags=draft.review_flags,causes=section('원인·판단 근거');
    if(flags.origin_query?.question){
      const origin=section('연결된 원질문');
      origin.append(el('p','',flags.origin_query.question),el('p','section-note','질문 기록 '+flags.origin_query.query_id+' · 질문과 현장 조치 근거를 함께 검토하세요.'));
      box.append(origin);
    }
    const reported=flags.reported_causes||[];
    causes.append(el('p','',reported.length?reported.map(item=>(item.certainty||'확인 상태 미기재')+' · '+item.note).join('\n'):'별도 원인 기록 없음 · 원본 근무일지를 확인하세요.'));box.append(causes);
    const observations=observationFields.filter(([key])=>flags.observations?.[key]);
    if(observations.length){const worker=section('작업자 판단·조건·안전 근거');worker.append(facts(observations.map(([key,label])=>[label,flags.observations[key]])));box.append(worker);}
    const normal=flags.normal_operation||{},normalSection=section('정상 운전 확인');
    normalSection.append(facts([['확인 상태',normalStates[normal.status]||'미확인'],['지속시간',normal.minutes===undefined?'미기재':normal.minutes+'분'],['확인 근거',normal.evidence]]),el('p','section-note','근무자가 기록한 관찰 결과입니다. 저장된 센서값만으로 연속 운전을 확정하지 않습니다.'));box.append(normalSection);
    if(flags.safety_report?.text){const safety=section('발견한 위험·주의사항');safety.append(el('p','',flags.safety_report.text));box.append(safety);}
    const history=section('근무자별 조치 경과'),list=el('ol','review-history'),items=timeline(draft);
    for(const item of items){
      const row=el('li'),context=item.required_context||{};
      row.append(el('h4','',context.author||'근무자 미기재'),el('p','history-context',stamp(context.start_at)+' – '+stamp(context.end_at)+' · '+(outcomes[item.record.outcome]||'상태 미기재')),
        el('p','',item.record.story||''),renderSteps(item.record));
      for(const [key,label] of [['remaining_issue','남은 문제'],['next_check','다음 확인 내용'],['next_check_at','확인 시점'],['follow_up','다음 근무 요청']]){
        if(item.record[key])row.append(el('p','',label+': '+item.record[key]));
      }
      list.append(row);
    }
    if(!items.length)history.append(renderSteps({action_steps:flags.action_steps||[]}));else history.append(list);box.append(history);
    const sourceSection=section('원본 근무일지·측정 근거');
    const recordRefs=new Map();
    for(const ref of draft.card.provenance?.sources||[]){
      const index=/^work_report\.records\[(\d+)\]$/.exec(ref.locator||'');
      if(index){if(!recordRefs.has(ref.source_id))recordRefs.set(ref.source_id,new Set());recordRefs.get(ref.source_id).add(Number(index[1]));}
    }
    for(const source of draft.sources||[]){
      const context=source.required_context||{},sourceBox=disclosure((context.author||'근무자 미기재')+' · '+stamp(context.start_at)+' · '+source.handover_id);
      sourceBox.append(facts([['근무자',context.author],['근무시간',stamp(context.start_at)+' – '+stamp(context.end_at)],['저장시각',stamp(source.created_at)]]));
      for(const [index,record] of (source.work_report?.records||[]).entries()){
        if(recordRefs.has(source.handover_id)&&!recordRefs.get(source.handover_id).has(index))continue;
        sourceBox.append(el('p','','발생시각: '+stamp(record.occurred_at)),el('p','',record.story||''),renderSteps(record));
        for(const cause of record.causes||[])sourceBox.append(el('p','',(cause.certainty||'')+' · '+cause.note));
        if(record.normal_run_evidence)sourceBox.append(el('p','','정상 운전 확인: '+record.normal_run_evidence));
        const workerFields=[...observationFields,['remaining_issue','남은 문제'],['next_check','다음 확인 내용'],['next_check_at','확인 시점'],
          ['follow_up','다음 근무 요청'],['references','참고 자료']].filter(([key])=>record[key]);
        if(workerFields.length)sourceBox.append(facts(workerFields.map(([key,label])=>[label,record[key]])));
      }
      if(source.memo_text&&!source.work_report)sourceBox.append(el('p','',source.memo_text));
      const measurements=source.server_sensor_evidence?.measurements||[];
      if(measurements.length){const readings=disclosure('저장 시점 측정값 '+measurements.length+'건');for(const m of measurements)readings.append(el('p','',
        (m.name||m.signal)+' · '+(m.value??'미수신')+' '+(m.unit||'')+' · '+stamp(m.observed_at)+' · 품질 '+(m.quality||'미기재')));sourceBox.append(readings);}
      if(source.work_report?.mes_context){const imported=disclosure('근무일지에 첨부한 MES 기록');imported.append(el('pre','',source.work_report.mes_context));sourceBox.append(imported);}
      sourceSection.append(sourceBox);
    }
    if(!draft.sources?.length)sourceSection.append(el('p','section-note','연결된 근무일지 원본이 없습니다. 초안의 근거를 확인하세요.'));box.append(sourceSection);
    const preview=section('지식카드 초안'),previewBox=disclosure('초안 내용·판단 근거 보기');previewBox.append(el('p','',draft.card.know_how),el('p','',draft.card.rationale));
    if(draft.card.conditions?.length)previewBox.append(el('p','','적용 조건: '+draft.card.conditions.map(c=>[c.field||c.signal,c.op,c.value].filter(v=>v!==undefined).join(' ')).join('\n')));
    preview.append(previewBox);box.append(preview);
    const publication=flags.publication;
    if(publication){
      const progress=section('지식카드 검색 반영'),state=el('p','',publicationStates[publication.state]||'상태 확인 필요');state.id='publication-state';
      const search=el('p','section-note',publication.state==='published'&&publication.searchable?'후속 질문의 검색 후보로 사용':'아직 검색에 사용하지 않음');search.id='publication-search';
      progress.append(state,search,facts([['검수 시각',stamp(publication.quality_checked_at)],['임베딩 모델',publication.model],['벡터 차원',publication.dimension]]));
      if(publication.error)progress.append(el('p','',publication.error));
      if(publication.state==='embedding_failed'&&publication.retry_at)progress.append(el('p','section-note','다음 시도: '+stamp(new Date(publication.retry_at*1000).toISOString())));
      const structured=disclosure('구조화된 카드 보기'),json=el('pre','',JSON.stringify(publication.card,null,2));json.id='publication-json';structured.append(json);progress.append(structured);box.append(progress);
    }
    const form=el('form','review-decision');form.id='review-decision-form';
    form.append(el('h3','','검토 처리'),el('p','','검토 승인 후 적용 조건·안전·원문을 확인해 검수 통과를 처리하세요. 임베딩 완료 후 검색에 반영됩니다.'));
    const label=el('label','','검토 의견'),reason=el('textarea');label.htmlFor='review-reason';reason.id='review-reason';reason.maxLength=2000;reason.placeholder='보완·반려 사유 또는 검수한 근거를 작성하세요.';form.append(label,reason);
    const actions=el('div','review-actions');
    const decisions=[['approve','검토 승인','approve-button'],['request_changes','보완 요청',''],['reject','반려','reject-button']];
    if(draft.status==='review_approved')decisions.unshift(['quality_pass','검수 통과','approve-button']);
    for(const [action,text,style] of decisions){
      const button=el('button',style,text);button.type='submit';button.dataset.action=action;actions.append(button);
    }
    form.append(actions);form.addEventListener('submit',event=>{event.preventDefault();decide(event.submitter?.dataset.action,reason.value);});box.append(form);
    const reviews=section('검토 이력');
    for(const item of [...draft.reviews].reverse()){
      const row=el('article','review-audit');row.append(el('h4','',status(item.status)+' · '+item.reviewer_name),el('p','',stamp(item.created_at)),el('p','',item.reason||'별도 의견 없음'));reviews.append(row);
    }
    if(!draft.reviews.length)reviews.append(el('p','section-note','아직 검토 이력이 없습니다.'));box.append(reviews);
  }
  async function loadDetail(id,focus=false){
    selected=id;const requestId=++detailRequest;renderList();$('candidate-detail').setAttribute('aria-busy','true');
    $('candidate-detail').replaceChildren(el('p','review-empty','후보 근거를 불러오는 중…'));
    try{const data=await request('/api/admin/card-drafts/'+encodeURIComponent(id));if(requestId!==detailRequest||!token)return;renderDetail(data.draft);if(focus&&innerWidth<=760)$('candidate-detail').scrollIntoView({block:'start'});}
    catch(error){if(requestId===detailRequest){detail=null;message(errorText(error),true);if(token)$('candidate-detail').replaceChildren(el('p','review-empty','후보를 불러오지 못했습니다. 목록에서 다시 선택하거나 새로고침하세요.'));}}
    finally{if(requestId===detailRequest)$('candidate-detail').removeAttribute('aria-busy');}
  }
  async function loadList(){
    const version=++listRequest;$('review-refresh').disabled=true;message('');
    try{const data=await request('/api/admin/card-drafts');if(version!==listRequest||!token)return;drafts=data.drafts.slice().sort((a,b)=>b.created_at.localeCompare(a.created_at));renderList();const item=filtered().find(item=>item.draft_id===selected)||filtered()[0];if(item)await loadDetail(item.draft_id);else{detail=null;selected=null;$('candidate-detail').replaceChildren(el('p','review-empty','목록에서 검토할 후보를 선택하세요.'));}}
    catch(error){message(errorText(error),true);}
    finally{$('review-refresh').disabled=false;}
  }
  async function decide(action,reason){
    if(saving||!detail||!action)return;
    if(action!=='approve'&&!reason.trim()){message('보완·반려 사유 또는 검수 근거를 입력해 주세요.',true);$('review-reason').focus();return;}
    const id=detail.draft_id,revision=detail.revision;saving=true;
    document.querySelectorAll('.review-actions button,#candidate-list button,#review-refresh').forEach(button=>{button.disabled=true;});
    try{
      const data=await request('/api/admin/card-drafts/'+encodeURIComponent(id)+'/review',{action,reason,expected_revision:revision});
      if(selected!==id||!token)return;drafts=drafts.map(item=>item.draft_id===id?data.draft:item);$('candidate-status').value='all';renderList();renderDetail(data.draft);
      message(status(data.draft.status)+'으로 처리했습니다.'+(action==='approve'?' 이어서 검수를 진행할 수 있습니다.':action==='quality_pass'?' 임베딩 완료 후 검색에 반영됩니다.':''));
    }catch(error){
      if(error.status===409&&token){await loadDetail(id);if($('review-reason'))$('review-reason').value=reason;}
      message(errorText(error),true);
    }finally{saving=false;document.querySelectorAll('.review-actions button,#candidate-list button,#review-refresh').forEach(button=>{button.disabled=false;});}
  }
  $('review-login-form').addEventListener('submit',async event=>{
    event.preventDefault();const button=event.submitter;button.disabled=true;
    const password=$('review-admin-password').value;$('review-admin-password').value='';
    try{const data=await request('/api/admin/login',{id:$('review-admin-id').value.trim(),password});session(data.token);await loadList();}
    catch(error){message(errorText(error),true);}finally{button.disabled=false;}
  });
  $('review-logout').addEventListener('click',async()=>{if(saving)return;try{await request('/api/admin/logout',{});session('');message('로그아웃했습니다.');}catch(error){message(errorText(error),true);}});
  $('review-refresh').addEventListener('click',()=>{if(!saving)loadList();});
  for(const id of ['candidate-search','candidate-status','candidate-type'])$(id).addEventListener(id==='candidate-search'?'input':'change',()=>{
    if(saving)return;renderList();const item=filtered().find(item=>item.draft_id===selected)||filtered()[0];if(item&&item.draft_id!==selected)loadDetail(item.draft_id);else if(!item){selected=null;detail=null;detailRequest++;$('candidate-detail').replaceChildren(el('p','review-empty','조건에 맞는 후보가 없습니다.'));}
  });
  session(token);if(token)loadList();
  setInterval(()=>{
    const state=detail?.review_flags?.publication?.state;
    if(token&&!saving&&document.visibilityState==='visible'&&['embedding_pending','embedding_running','embedding_failed'].includes(state)&&!$('review-reason')?.value.trim())loadDetail(selected);
  },5000);
})();
