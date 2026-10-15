// Local Figma plugin. Finalize audited v2 details without changing the original backup.
async function finalizeV2(){
 figma.showUI('<pre id="out">검수 보완 시작…</pre><script>onmessage=e=>out.textContent=typeof e.data.pluginMessage==="string"?e.data.pluginMessage:JSON.stringify(e.data.pluginMessage,null,2);</script>',{width:620,height:580});
 const progress=value=>figma.ui.postMessage(value);
 const page=figma.root.children.find(p=>p.name==='02. 2차 시안');
 if(!page)throw Error('2차 시안 페이지가 없습니다.');
 if(figma.currentPage!==page)await figma.setCurrentPageAsync(page);
 const all=r=>r.findAll(()=>true),texts=r=>r.findAll(n=>n.type==='TEXT');
 const screens=all(page).filter(n=>n.type==='FRAME'&&n.width===1280&&n.height===800&&!n.name.includes('presentation'));
 const screen=p=>screens.find(n=>n.name.startsWith(p));
 const fonts=new Map();for(const t of texts(page))for(const segment of t.getStyledTextSegments(['fontName']))fonts.set(JSON.stringify(segment.fontName),segment.fontName);
 await Promise.all([...fonts.values()].map(f=>figma.loadFontAsync(f)));
 let backup=figma.root.children.find(p=>p.name==='02. 2차 시안 · 최종 검수 전 백업 · 2026-10-15T06:19:14.396Z');if(!backup){backup=page.clone();backup.name='02. 2차 시안 · 최종 검수 전 백업 · '+new Date().toISOString();}progress('폰트 확인 완료 · 설비별 연결 보완 중');
 const changed=new Set(),created=new Set(),variables=[];
 const mark=n=>{changed.add(n.id);return n;};
 const paint=hex=>[{type:'SOLID',color:{r:parseInt(hex.slice(0,2),16)/255,g:parseInt(hex.slice(2,4),16)/255,b:parseInt(hex.slice(4,6),16)/255}}];
 const visible=n=>{for(let p=n;p&&p!==page;p=p.parent)if('visible'in p&&!p.visible)return false;return true;};
 const label=n=>texts(n).filter(visible).map(t=>t.characters).join(' ').trim();
 const buttons=r=>all(r).filter(n=>(n.type==='FRAME'||n.type==='INSTANCE')&&/^Button/.test(n.name));
 async function click(n,actions){const reactions=(n.reactions||[]).filter(r=>!r.trigger||r.trigger.type!=='ON_CLICK');reactions.push({trigger:{type:'ON_CLICK'},actions});await n.setReactionsAsync(reactions);mark(n);}
 const nav=to=>({type:'NODE',destinationId:to.id,navigation:'NAVIGATE',transition:null});
 // Starter plan permits a single action: use equipment-specific frame destinations.
 const history=screen('06 ');history.name='06 정비이력 · 선택 설비';mark(history);
 const collections=await figma.variables.getLocalVariableCollectionsAsync();
 const prototype=collections.find(c=>c.name==='ShiftLink · prototype state');
 const oldVars=prototype?await figma.variables.getLocalVariablesAsync('STRING'):[];
 const variableIds=new Set(oldVars.filter(v=>v.variableCollectionId===prototype.id).map(v=>v.id));
 for(const t of texts(page))if(t.boundVariables&&t.boundVariables.characters&&variableIds.has(t.boundVariables.characters.id)){t.setBoundVariable('characters',null);mark(t);}
 const typeNames={HPU:'유압 장치',COMP:'공기 압축기',PUMP:'순환 펌프'};
 let board=screen('05 ');while(board.parent!==page)board=board.parent;
 let bottom=Math.max(...board.children.filter(n=>! / · (HPU|COMP|PUMP) \d{2}$/.test(n.name)).map(n=>n.y+n.height))+160,index=0;
 for(const b of buttons(screen('04 '))){const number=label(b);if(!/^\d{2}$/.test(number))continue;let owner=b.parent,type;while(owner&&owner!==screen('04 ')){type=texts(owner).find(t=>t.parent.name==='Type'&&typeNames[t.characters]);if(type)break;owner=owner.parent;}if(!type)continue;
  const equipment=type.characters+' '+number,description=typeNames[type.characters];
  let expanded=screen('05 '),collapsed=screen('05B '),detail=history;
  if(equipment!=='HPU 01'){
   const group=[];for(const source of [expanded,collapsed,detail]){let clone=screens.find(n=>n.name===source.name+' · '+equipment);if(!clone){clone=source.clone();clone.name=source.name+' · '+equipment;board.appendChild(clone);for(const n of [clone,...all(clone)])created.add(n.id);}group.push(clone);}
   [expanded,collapsed,detail]=group;
   group.forEach((f,col)=>{f.x=32+col*1344;f.y=bottom+index*960;mark(f);for(const t of texts(f)){if(t.boundVariables&&t.boundVariables.characters)t.setBoundVariable('characters',null);const value=t.characters.replace(/HPU 01/g,equipment).replace(/유압 장치/g,description);if(value!==t.characters){t.characters=value;mark(t);}}});index++;
  }
  for(const [s,other] of [[expanded,collapsed],[collapsed,expanded]])for(const child of buttons(s)){
   const value=label(child);if(value==='정비이력')await click(child,[nav(detail)]);
   if(/^채팅 (숨기기|열기)$/.test(value))await click(child,[nav(other)]);
   if(/^인계\s?사항 확인$/.test(value))await click(child,[nav(screen('06A '))]);
  }
  await click(b,[nav(expanded)]);progress(equipment+' 화면·이력 연결 완료');
 }
 board.resizeWithoutConstraints(Math.max(board.width,4096),Math.max(board.height,bottom+index*960));mark(board);
 // Correct handover button destinations; presentation wrappers are never navigation targets.
 for(const s of [screen('05 '),screen('05B ')])for(const b of buttons(s)){
  const text=label(b);if(/^인계\s?사항 확인$/.test(text))await click(b,[nav(screen('06A '))]);
  if(text==='정비이력')await click(b,[nav(history)]);
 }
 for(const s of screens){
  const active=/^(04 |05 |05B |06 |06B )/.test(s.name)?'설비 목록':/^11 /.test(s.name)?'설비 스캔':null;
  const header=all(s).find(n=>n.name==='Global navigation');if(header)for(const b of buttons(header)){const text=label(b);if(!['설비 목록','설비 스캔'].includes(text))continue;const selected=text===active;b.fills=paint(selected?'397F7C':'FFFFFF');b.strokes=paint(selected?'397F7C':'DDE5E5');mark(b);for(const t of texts(b)){t.fills=paint(selected?'FFFFFF':'182C31');mark(t);}}
  const colors={'조치필요':['FFF0D9','91530A'],'조치중':['E5EEFF','274D94'],'경과관찰':['F1E8FF','69429C'],'조치완료':['DDF3E6','246442']};
  for(const t of texts(s)){const c=colors[t.characters.replace(/\s/g,'')];if(c&&t.parent.type==='FRAME'){t.fills=paint(c[1]);t.parent.fills=paint(c[0]);mark(t);mark(t.parent);}}
 }
 // A real vector checkbox avoids platform emoji colors and provides a 44px touch target.
 const checkboxSvg=checked=>'<svg width="20" height="20" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><rect x="1" y="1" width="18" height="18" rx="3" fill="'+(checked?'#397F7C':'#FFFFFF')+'" stroke="#397F7C" stroke-width="1.5"/>'+(checked?'<path d="m5 10 3 3 7-7" fill="none" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>':'')+'</svg>';
 for(const s of screens.filter(s=>/^(07 |08 |08B )/.test(s.name))){
  const old=texts(s).find(t=>t.parent.name==='List header'&&/선택/.test(t.characters));
  if(old&&!all(s).some(n=>n.name==='Header checkbox target')){
   const parent=old.parent,index=parent.children.indexOf(old),target=figma.createFrame();created.add(target.id);target.name='Header checkbox target';parent.insertChild(index,target);target.layoutMode='HORIZONTAL';target.resize(70,44);target.primaryAxisSizingMode='FIXED';target.counterAxisSizingMode='FIXED';target.primaryAxisAlignItems='MIN';target.counterAxisAlignItems='CENTER';target.itemSpacing=6;target.fills=[];
   const icon=figma.createNodeFromSvg(checkboxSvg(/^08B /.test(s.name)));target.appendChild(icon);created.add(icon.id);
   const t=figma.createText();target.appendChild(t);created.add(t.id);t.fontName=old.fontName;t.fontSize=12;t.characters='선택';t.fills=paint('397F7C');
   old.visible=false;mark(old);if(parent.layoutMode==='HORIZONTAL')parent.counterAxisSizingMode='AUTO';mark(parent);
   await click(target,[nav(/^08B /.test(s.name)?screen('07 '):screen('08B '))]);
  }
  for(const t of texts(s).filter(t=>visible(t)&&/^[☑□]$/.test(t.characters))){const parent=t.parent,index=parent.children.indexOf(t),icon=figma.createNodeFromSvg(checkboxSvg(t.characters==='☑'));parent.insertChild(index,icon);created.add(icon.id);t.visible=false;mark(t);}
 }
 const local=new Map(all(page).map(n=>[n.id,n])),bad=[];let routes=0;
 for(const n of all(page).filter(n=>'reactions'in n))for(const r of n.reactions)for(const a of(r.actions||[]))if(a.type==='NODE'&&a.navigation!=='CHANGE_TO'){routes++;const d=local.get(a.destinationId);if(d&&d.name.includes('presentation')){const actual=d.findAll?d.findAll(x=>x.type==='FRAME'&&x.width===1280&&x.height===800&&!x.name.includes('presentation'))[0]:null;if(actual){const reactions=n.reactions.map(r=>({...r,actions:(r.actions||[]).map(x=>x.type==='NODE'&&x.destinationId===d.id?{...x,destinationId:actual.id}:x)}));await n.setReactionsAsync(reactions);mark(n);continue;}}if(!d||d.name.includes('presentation'))bad.push({node:n.id,name:n.name,to:a.destinationId,destination:d&&d.name});}
 if(bad.length)throw Error('남은 화면 연결 확인 필요: '+JSON.stringify(bad));
 const result={status:'최종 보완 적용',backup:backup.name,createdNodeIds:[...created],mutatedNodeIds:[...changed],variableIds:variables,screenCount:all(page).filter(n=>n.type==='FRAME'&&n.width===1280&&n.height===800&&!n.name.includes('presentation')).length,checkedRoutes:routes,badRoutes:bad};
 console.log(JSON.stringify(result));
 figma.ui.postMessage(result);
}
finalizeV2().catch(e=>{figma.showUI('<pre id="out"></pre><script>onmessage=e=>out.textContent=e.data.pluginMessage;</script>',{width:620,height:500});figma.ui.postMessage(String(e));});
