/* ShiftLink Figma Plugin API script — 2026-10-15.
 * Run inside Figma/Scripter, never in the browser console.
 * Only the page named '02. 2차 시안' is changed; a page clone is kept first.
 * No network, credentials, external assets, or comment mutations.
 * APPLY=false performs inventory/preflight only.
 */
const APPLY = true;
const report = value => typeof print === 'function' ? print(value) : console.log(value);
async function patchShiftLinkV2() {
  const page = figma.root.children.find(p => p.name === '02. 2차 시안');
  if (!page) throw new Error('02. 2차 시안 페이지가 없어 중단합니다.');
  await figma.setCurrentPageAsync(page);
  const all = root => root.findAll(() => true);
  const texts = root => root.findAll(n => n.type === 'TEXT');
  const match = (root, name) => all(root).find(n => n.name === name);
  const screens = all(page).filter(n => n.type === 'FRAME' && n.width === 1280 && n.height === 800);
  const screen = prefix => screens.find(n => n.name.startsWith(prefix) && !n.name.includes('presentation'));
  const required = ['01 ', '02 ', '03 ', '05 ', '05B ', '06 ', '06A ', '07 ', '08 ', '08B ', '10B ', '10C ', '11 '];
  const missing = required.filter(prefix => !screen(prefix));
  const inventory = screens.map(n => ({id:n.id, name:n.name, width:n.width, height:n.height}));
  if (missing.length) throw new Error('화면 이름 확인 필요: '+missing.join(', ')+'\n'+JSON.stringify(inventory));
  const reports=screens.filter(s=>/^(07 |08 |08B )/.test(s.name));
  const reportHeadings=new Map();
  for(const s of reports) {
    const heading=texts(s).find(t=>/^(설비를 선택하세요|선택|[□▣☑] 선택)$/.test(t.characters)&&t.parent&&/^(List header|.*heading.*)$/i.test(t.parent.name));
    if(!heading)throw new Error('#50: '+s.name+' 표 헤더 선택 열 확인 필요. 변경 없이 중단합니다.');
    reportHeadings.set(s.id,heading);
  }
  let board=screen('06 ');
  while(board.parent&&board.parent!==page)board=board.parent;
  if(!['FRAME','SECTION'].includes(board.type)||board===screen('06 '))throw new Error('2차 보드 FRAME 구조 확인 필요. 변경 없이 중단합니다.');
  if (!APPLY) { report(JSON.stringify({mode:'PREFLIGHT_ONLY',page:page.id,screens:inventory},null,2)); return; }
  const fontNames = new Map();
  for (const t of texts(page)) for (const s of t.getStyledTextSegments(['fontName'])) fontNames.set(JSON.stringify(s.fontName),s.fontName);
  await Promise.all([...fontNames.values()].map(f => figma.loadFontAsync(f)));
  const available = await figma.listAvailableFontsAsync();
  const bodyFont = available.find(f => f.fontName.family === 'Noto Sans KR' && f.fontName.style === 'Regular');
  if (!bodyFont) throw new Error('Noto Sans KR Regular 폰트가 없어 중단합니다.');
  await figma.loadFontAsync(bodyFont.fontName);
  const backup = page.clone(); backup.name = '02. 2차 시안 · 코드 적용 전 백업 · '+new Date().toISOString();
  const changed = new Set(), created = new Set(), warnings = [];
  const mark = n => { changed.add(n.id); return n; };
  const rgb = hex => ({r:parseInt(hex.slice(0,2),16)/255,g:parseInt(hex.slice(2,4),16)/255,b:parseInt(hex.slice(4,6),16)/255});
  const paint = hex => [{type:'SOLID',color:rgb(hex)}];
  const teal='397F7C', ink='182C31', muted='587174', paper='FFFFFF', line='DDE5E5';
  const put = (t,value) => {t.characters=value; mark(t);};
  const hide = n => {if(n){n.visible=false;mark(n);}};
  const visible = n => {for(let p=n;p&&p!==page;p=p.parent)if('visible' in p&&!p.visible)return false;return true;};
  const caption = n => texts(n).filter(visible).map(t=>t.characters).join(' ');
  const button = (root,label) => all(root).find(n => (n.type==='INSTANCE'||n.type==='FRAME') && /^Button/.test(n.name) && caption(n)===label);
  async function navigate(n,to) {
    if(!n){warnings.push('연결할 버튼을 찾지 못함: '+to);return;}
    const reactions=(n.reactions||[]).filter(r=>r.trigger && r.trigger.type!=='ON_CLICK');
    reactions.push({trigger:{type:'ON_CLICK'},actions:[to==='BACK'?{type:'BACK'}:{type:'NODE',destinationId:to.id,navigation:'NAVIGATE',transition:null}]});
    await n.setReactionsAsync(reactions);mark(n);
  }
  function text(parent,name,value,size=16,color=ink) {
    const n=figma.createText();created.add(n.id);parent.appendChild(n);n.name=name;n.fontName=bodyFont.fontName;
    n.characters=value;n.fontSize=size;n.lineHeight={unit:'PIXELS',value:size*1.5};n.fills=paint(color);return n;
  }
  function stack(parent,name,direction,width,height) {
    const n=figma.createFrame();created.add(n.id);parent.appendChild(n);n.name=name;n.layoutMode=direction;
    n.resize(width,height);n.primaryAxisSizingMode='FIXED';n.counterAxisSizingMode='FIXED';n.fills=[];return n;
  }
  async function backIcon(original) {
    if(!original)return;
    let n=original.type==='INSTANCE'?original.detachInstance():original;mark(n);
    for(const child of n.children)hide(child);
    n.name='Button / 뒤로가기 아이콘';n.resize(56,56);n.paddingLeft=n.paddingRight=n.paddingTop=n.paddingBottom=16;
    n.primaryAxisAlignItems='CENTER';n.counterAxisAlignItems='CENTER';n.fills=paint(paper);n.strokes=paint(line);
    const svg=figma.createNodeFromSvg('<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 10a8 8 0 1 1 1 8M4 10V4m0 6h6" stroke="#397F7C" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>');
    n.appendChild(svg);created.add(svg.id);svg.name='반시계 뒤로가기';await navigate(n,'BACK');return n;
  }
  // #48 selected navigation styling; #51 distinct action-status colors.
  const statusColors={'조치 필요':['FFF0D9','91530A'],'조치 중':['E5EEFF','274D94'],'경과 관찰':['F1E8FF','69429C'],'조치 완료':['DDF3E6','246442']};
  for(const s of screens) {
    const nav=match(s,'Global navigation');
    if(nav)for(const n of all(nav).filter(n=>n.type==='INSTANCE'&&/^Button/.test(n.name))) {
      const label=caption(n), selected=(label==='설비 목록'&&/^04 /.test(s.name))||(label==='설비 스캔'&&/^11 /.test(s.name));
      n.fills=paint(selected?teal:paper);n.strokes=paint(selected?teal:line);mark(n);
      for(const t of texts(n)){t.fills=paint(selected?paper:ink);mark(t);}
    }
    for(const t of texts(s)) {
      const colors=statusColors[t.characters.trim()];
      if(colors&&t.parent&&t.parent.type==='FRAME'){t.parent.fills=paint(colors[0]);t.fills=paint(colors[1]);mark(t);mark(t.parent);}
    }
    const backs=all(s).filter(n=>(n.type==='INSTANCE'||n.type==='FRAME')&&/^Button/.test(n.name)&&/^(뒤로\s?가기|이전)$/.test(caption(n)));
    for(const n of backs)await backIcon(n); // #53
  }
  // #47 existing factory image becomes the full-screen landing background.
  const landing=screen('01 '), hero=match(landing,'Welcome');
  if(!hero||!Array.isArray(hero.fills)||!hero.fills.some(p=>p.type==='IMAGE'))warnings.push('#47: Welcome의 공장 이미지 fill 확인 필요');
  else {
    landing.fills=hero.fills.map(p=>({...p}));mark(landing);hero.fills=[];mark(hero);
    for(const n of [match(landing,'Global navigation'),match(landing,'Main content'),match(landing,'Connection status')])if(n){n.fills=[];mark(n);}
    for(const t of texts(hero)){t.fills=paint(paper);mark(t);}
  }
  // #44 account login → face-login alternative → keyboard (last).
  const account=screen('02 '), login=button(account,'로그인'), face=button(account,'얼굴 인식으로 로그인');
  if(login&&face&&login.parent===face.parent){const p=login.parent;p.insertChild(p.children.indexOf(login)+1,face);mark(p);}
  else warnings.push('#44: 로그인/얼굴 로그인 버튼의 동일 부모 구조 확인 필요');
  const keyboard=all(account).find(n=>n.type==='FRAME'&&/keyboard/i.test(n.name));
  if(keyboard){keyboard.parent.appendChild(keyboard);mark(keyboard.parent);}else warnings.push('#44: 자판 그룹 이름 확인 필요');
  // #45 home CTA right-aligned; #46 handover card hugs its actual content.
  const home=screen('03 '), summary=match(home,'Home summary'), overview=match(home,'Overview panels');
  if(summary){summary.resize(1216,summary.height);summary.primaryAxisAlignItems='SPACE_BETWEEN';mark(summary);const info=summary.children.find(n=>n.type==='FRAME');if(info){info.layoutSizingHorizontal='FILL';mark(info);}}
  const homeCta=button(home,'근무일지 작성 →')||button(home,'근무일지 작성');if(homeCta){homeCta.resize(256,56);mark(homeCta);}
  if(overview){overview.counterAxisAlignItems='MIN';mark(overview);}
  const handover=match(home,'인계사항');if(handover){handover.primaryAxisSizingMode='AUTO';handover.layoutSizingVertical='HUG';mark(handover);}
  // #49/#50/#52/#54 report labels, date row and a green table-header selector.
  const empty=screen('07 '), full=screen('08B ');
  for(const s of reports) {
    for(const t of texts(s)) {
      if(t.characters==='설비를 선택하세요')put(t,'선택');
      if(t.characters==='이번 근무')hide(t.parent&&t.parent.name.includes('Tag')?t.parent:t);
      if(t.characters==='근무 일지 작성'||t.characters==='근무일지 작성')put(t,'근무일지 작성   2026-10-14 08:00 ~16:00');
      if(/2026\.10\.14\s+08:00/.test(t.characters))hide(t);
      if(t.characters==='☑'||t.characters==='□'){t.fills=paint(teal);mark(t);}
    }
    const heading=reportHeadings.get(s.id), isFull=/^08B /.test(s.name);
    put(heading,isFull?'☑ 선택':/^08 /.test(s.name)?'▣ 선택':'□ 선택');
    heading.fills=paint(teal);mark(heading);await navigate(heading,isFull?empty:full);
    const old=button(s,'전체 선택')||button(s,'전체 선택 해제');hide(old);
  }
  // #56/#57 equipment-specific maintenance history, independent from all-duty logs.
  const history=screen('06 '), historyBody=match(history,'Main content');
  const title=texts(history).find(t=>t.characters==='당직일지');if(title)put(title,'정비이력 · HPU 01');
  const equipmentTitle=texts(history).find(t=>t.characters.startsWith('인계 설비 ·'));if(equipmentTitle)put(equipmentTitle,'HPU 01 · 유압 장치');
  const rows=all(history).filter(n=>n.type==='FRAME'&&/^Timeline \d/.test(n.name));
  const actionTexts=['HPU 01 · 유압 저하 확인, 다음 근무 재점검','HPU 01 · 배관 누유 점검, 이상 없음','HPU 01 · 부하 운전 시 압력 추이 관찰'];
  rows.forEach((row,i)=>{const ts=texts(row);if(ts.length>=3)put(ts[2],actionTexts[i]||actionTexts[0]);});
  const ack=button(history,'인계사항 확인')||button(history,'인계 사항 확인');await backIcon(ack);
  const chat=screen('05 '), collapsed=screen('05B '), allDuty=screen('06A ');
  warnings.push('#56: 정비이력 연결은 05/05B의 HPU 01 예시 선택에 한정합니다. 다른 설비의 이력 지원은 구현하지 않습니다.');
  for(const s of [chat,collapsed])await navigate(button(s,'정비이력'),history);
  // #63 all-duty rows keep opening the duty-log detail, not the equipment history.
  let duty=screen('06D ');
  if(!duty){duty=history.clone();created.add(duty.id);duty.name='06D 인계사항 · 당직일지 상세';}
  const boardBottom=Math.max(0,...board.children.filter(n=>n!==duty).map(n=>n.y+n.height));
  board.appendChild(duty);
  if('layoutMode' in board&&board.layoutMode!=='NONE')duty.layoutPositioning='ABSOLUTE';
  duty.x=32;duty.y=boardBottom+160;mark(duty);
  board.resizeWithoutConstraints(Math.max(board.width,duty.x+duty.width+32),Math.max(board.height,duty.y+duty.height+160));mark(board);
  const dt=texts(duty).find(t=>t.characters==='정비이력 · HPU 01');if(dt)put(dt,'당직일지');
  const de=texts(duty).find(t=>t.characters==='HPU 01 · 유압 장치');if(de)put(de,'인계 설비 · HPU 01 · COMP 02 · PUMP 03');
  const dutyRows=all(duty).filter(n=>n.type==='FRAME'&&/^Timeline \d/.test(n.name));
  const dutyActions=['HPU 01 · 유압 저하 확인, 다음 근무 재점검','COMP 02 · 베어링 진동 점검 진행 중','PUMP 03 · 씰 교체 완료, 다음 근무 누유 관찰'];
  dutyRows.forEach((r,i)=>{const ts=texts(r);if(ts.length>=3)put(ts[2],dutyActions[i]||dutyActions[0]);});
  for(const s of [home,allDuty])for(const row of all(s).filter(n=>n.type==='FRAME'&&/handover$/.test(n.name))) {
    const clickable=all(row).filter(n=>'reactions' in n&&n.reactions.some(r=>r.trigger&&r.trigger.type==='ON_CLICK'));
    await navigate(row,duty);
    for(const n of clickable)await navigate(n,duty);
  }
  await backIcon(button(allDuty,'당직일지 열기'));
  // #58/#62 scanner and face layouts share the same explicit stage/button anchors.
  for(const s of [screen('10B '),screen('10C '),screen('11 ')]) {
    const body=match(s,'Main content')||all(s).find(n=>n.type==='FRAME'&&n.width===1280&&n.height>=700);
    if(!body){warnings.push('#58/#62: '+s.name+' 본문 확인 필요');continue;}
    body.layoutMode='NONE';mark(body);
    const isFace=/^10/.test(s.name), stage=all(body).find(n=>(n.type==='FRAME'||n.type==='ELLIPSE')&&n.width>=380&&n.height>=380);
    const prompt=texts(body).find(t=>/얼굴|화면 안에/.test(t.characters));
    if(prompt){if(isFace)put(prompt,'화면 중앙에 얼굴을 맞춰주세요');prompt.resize(960,40);prompt.x=160;prompt.y=48;prompt.textAlignHorizontal='CENTER';mark(prompt);}
    if(stage){stage.resize(isFace?464:960,isFace?464:520);stage.x=isFace?408:160;stage.y=isFace?140:112;mark(stage);}
    const action=button(s,'인식 완료')||button(s,'재인식')||button(s,'설비 촬영');
    if(action){body.appendChild(action);action.resize(240,56);action.x=520;action.y=664;mark(action);}
    const back=all(s).find(n=>n.name==='Button / 뒤로가기 아이콘');if(back){body.appendChild(back);back.x=32;back.y=664;mark(back);}
  }
  // #59/#60/#61 use the empty right pane for MES data, remove duty-person metadata.
  const cb=match(collapsed,'Main content')||match(collapsed,'Equipment workspace'), funcs=match(collapsed,'Equipment functions')||(button(collapsed,'정비이력')||{}).parent;
  if(cb&&funcs){
    cb.layoutMode='HORIZONTAL';cb.itemSpacing=24;cb.paddingLeft=cb.paddingRight=32;mark(cb);
    funcs.resize(416,608);mark(funcs);
    for(const n of funcs.children)if(n.type==='FRAME'&&/duty|operator|근무|Current shift/i.test(n.name))hide(n);
    for(const t of texts(funcs))if(/^(이번 근무|김현장 · A조)$/.test(t.characters))hide(t);
    for(const n of funcs.children)if('resize' in n&&/^Button/.test(n.name)){n.resize(368,n.height);mark(n);}
    let panel=match(collapsed,'MES 센서 데이터');
    if(!panel){panel=stack(cb,'MES 센서 데이터','VERTICAL',776,608);panel.paddingLeft=panel.paddingRight=panel.paddingTop=panel.paddingBottom=24;panel.itemSpacing=16;panel.fills=paint(paper);panel.cornerRadius=16;
      text(panel,'MES 제목','MES 센서 데이터',20);text(panel,'MES 연결 안내','미연결 · 실제 MES 데이터 수신 전',16,muted);
      for(const labels of [['유압 · MPa','오일 온도 · °C','진동 · mm/s'],['전류 · A','유량 · L/min','전압 · V']]){const r=stack(panel,'MES 지표 행','HORIZONTAL',728,112);r.itemSpacing=16;for(const label of labels){const card=stack(r,label,'VERTICAL',232,112);card.paddingLeft=card.paddingRight=card.paddingTop=card.paddingBottom=16;card.fills=paint('F2F6F5');card.cornerRadius=12;text(card,'지표',label,16,muted);text(card,'값','—',28);}}
    }
  } else warnings.push('#59/#60: 05B Main content / Equipment functions 구조 확인 필요');
  figma.currentPage.selection=[];
  report(JSON.stringify({backup:backup.id,createdNodeIds:[...created],mutatedNodeIds:[...changed],warnings},null,2));
}
patchShiftLinkV2().catch(error=>report('ERROR: '+String(error)));
