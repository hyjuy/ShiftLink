/* Published cards and review candidates share a database, with separate states. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  const labels={published:'기준 KB',pending_review:'검토 대기',changes_requested:'보완 요청',review_approved:'검토 승인 · 검수 대기',quality_passed:'검수 통과',rejected:'반려'};
  const types={T3:'문제 해결',T4:'인계 해결 사례',T6:'재가동 경험'};
  let data=null,loading=null,loadedAt=0,selected='',error='';
  const el=(tag,cls,text)=>{const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=text;return node;};
  const screen=el('section','screen');screen.id='s-knowledge';
  screen.innerHTML='<div class="pane knowledge-pane"><header class="knowledge-heading"><div><p class="knowledge-eyebrow">현장 지식</p><h1>지식카드 관리</h1></div><button type="button" class="btn ghost" id="knowledgeBack">대시보드로</button></header><p class="hint">사용 중인 카드와 검토 중인 후보를 확인합니다. 후보 검토는 관리자 화면에서 진행합니다.</p><div class="knowledge-counts" id="knowledgeCounts"></div><div class="knowledge-controls"><label>카드 검색<input id="knowledgeSearch" type="search" placeholder="카드 번호, 설비, 제목"></label><label>상태<select id="knowledgeState"></select></label><button type="button" class="btn ghost" id="knowledgeRefresh">새로고침</button><a class="btn" href="/knowledge-candidates.html">관리자 검토</a></div><p id="knowledgeStatus" role="status"></p><div class="knowledge-columns"><div class="knowledge-list" id="knowledgeList" aria-label="지식카드 목록"></div><article class="knowledge-detail" id="knowledgeDetail" aria-live="polite"></article></div></div>';
  document.querySelector('.screen').parentNode.appendChild(screen);
  for(const [value,label] of Object.entries(labels)){
    const option=el('option','',label);option.value=value;$('knowledgeState').appendChild(option);
  }
  function items(){
    if(!data)return [];
    return [...data.cards.map(card=>({id:'card:'+card.card_id,card,status:'published'})),
      ...data.drafts.map(draft=>({id:'draft:'+draft.draft_id,card:draft.card,status:draft.status,draft}))];
  }
  function summary(){
    const gap=$('anGap');if(!gap)return;
    let panel=$('knowledgeDashboard');
    if(!panel){panel=el('section','knowledge-dashboard');panel.id='knowledgeDashboard';gap.appendChild(panel);}
    panel.replaceChildren();
    const counts=el('div','knowledge-summary');
    for(const [key,label] of [['published','기준 KB'],['pending_review','검토 대기'],['changes_requested','보완 요청']]){
      const cell=el('div');cell.append(el('strong','',data?String(data.summary[key]):'—'),el('span','',label));counts.appendChild(cell);
    }
    const open=el('button','btn','카드 목록 보기');open.type='button';open.id='knowledgeOpen';open.addEventListener('click',()=>{show('knowledge');render();load(true);});
    panel.append(counts,open);
    if(error)panel.append(el('p','knowledge-error',error));
  }
  function detail(item){
    const box=$('knowledgeDetail');box.replaceChildren();
    if(!item){box.append(el('h2','','카드를 선택하세요'),el('p','hint','목록에서 카드를 선택하면 원인·조치·출처를 확인할 수 있습니다.'));return;}
    const card=item.card;
    box.append(el('p','knowledge-state',labels[item.status]||'상태 확인 필요'),el('p','knowledge-id',card.card_id),el('h2','',card.title),
      el('p','hint',[card.equipment,card.component,types[card.tacit_type]||card.tacit_type].filter(Boolean).join(' · ')));
    for(const [label,text] of [['증상',card.symptom],['조치·노하우',card.know_how],['판단 근거',card.rationale]]){
      if(!text)continue;box.append(el('h3','',label),el('p','knowledge-text',text));
    }
    const sources=card.provenance?.sources||[];
    if(sources.length){box.append(el('h3','','출처'));for(const source of sources)box.append(el('p','knowledge-source',[source.source_id,source.locator].filter(Boolean).join(' · ')));}
    if(item.draft){
      const publication=item.draft.review_flags?.publication;
      if(publication){
        const states={embedding_pending:'임베딩 대기',embedding_running:'임베딩 중',embedding_failed:'임베딩 실패',published:'검색 반영 완료',superseded:'재검토로 검색 제외'};
        const lineState=states[publication.state]||'상태 확인 필요';
        box.append(el('h3','','검색 반영 상태'),el('p','knowledge-source',lineState+(publication.searchable?' · 적용 설비·조건은 질의 시 확인':' · 검색에 사용하지 않음')));
      }
      const origin=item.draft.review_flags?.work_report;
      if(origin?.handover_id)box.append(el('h3','','원본 근무일지'),el('p','knowledge-source',origin.handover_id+' · 기록 '+(origin.record_index+1)));
      const link=el('a','btn','관리자 검토 열기');link.href='/knowledge-candidates.html';box.append(link);
    }
  }
  function render(){
    const counts=$('knowledgeCounts');counts.replaceChildren();
    if(data)for(const [key,label] of Object.entries(labels))counts.append(el('span','',label+' '+(data.summary[key]||0)+'건'));
    $('knowledgeStatus').textContent=error||(loading?'지식카드를 불러오는 중…':data?'Jetson MES DB 기준':'');
    $('knowledgeStatus').className=error?'knowledge-error':'hint';
    const query=$('knowledgeSearch').value.trim().toLowerCase(),state=$('knowledgeState').value;
    const filtered=items().filter(item=>item.status===state&&(!query||[item.card.card_id,item.card.title,item.card.equipment,item.card.component].join(' ').toLowerCase().includes(query)));
    const list=$('knowledgeList');list.replaceChildren();
    if(!filtered.length){selected='';list.append(el('p','knowledge-empty',error?'연결을 확인한 뒤 새로고침해 주세요.':loading?'목록을 불러오는 중…':'조건에 맞는 카드가 없습니다.'));detail(null);return;}
    if(!filtered.some(item=>item.id===selected))selected=filtered[0].id;
    for(const item of filtered){
      const button=el('button','knowledge-row');button.type='button';button.dataset.cardId=item.card.card_id;button.setAttribute('aria-pressed',String(item.id===selected));
      button.append(el('span','knowledge-row-meta',item.card.card_id+' · '+(item.card.equipment||'공통')),el('strong','',item.card.title),el('span','knowledge-row-meta',labels[item.status]));
      button.addEventListener('click',()=>{selected=item.id;render();});list.appendChild(button);
    }
    detail(filtered.find(item=>item.id===selected));
  }
  async function load(force=false){
    if(loading)return loading;
    if(!force&&data&&Date.now()-loadedAt<30000)return;
    $('knowledgeRefresh').disabled=true;
    loading=(async()=>{
      try{data=await getJson('/api/knowledge-cards');loadedAt=Date.now();error='';}
      catch(_){data=null;error='지식카드 DB를 불러오지 못했습니다. 새로고침해 주세요.';}
      finally{loading=null;$('knowledgeRefresh').disabled=false;summary();if(S.screen==='knowledge')render();}
    })();
    if(S.screen==='knowledge')render();
    return loading;
  }
  $('knowledgeBack').addEventListener('click',()=>$('toDashboard').click());
  $('knowledgeSearch').addEventListener('input',()=>{selected='';render();});
  $('knowledgeState').addEventListener('change',()=>{selected='';render();});
  $('knowledgeRefresh').addEventListener('click',()=>load(true));
  // Keep main's knowledge-gap analytics and append the inventory after each dashboard render.
  document.addEventListener('shiftlink:knowledge-dashboard',()=>{summary();load();});
  summary();load();
})();
