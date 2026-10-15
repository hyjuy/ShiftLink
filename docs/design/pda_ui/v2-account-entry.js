// First entry is the existing account-login design; keep the old landing as an archive.
(async function(){
 const page=figma.root.children.find(p=>p.name==='02. 2차 시안');
 if(!page)throw Error('2차 시안 페이지가 없습니다.');
 await figma.setCurrentPageAsync(page);
 const landing=await figma.getNodeByIdAsync('115:309'),account=await figma.getNodeByIdAsync('115:341');
 if(!landing||!account||account.type!=='FRAME')throw Error('로그인 화면 확인 필요');
 let redirected=0;
 for(const n of page.findAll(n=>'reactions'in n)){
  const reactions=n.reactions.map(r=>({...r,actions:(r.actions||[]).map(a=>a.type==='NODE'&&a.destinationId===landing.id?{...a,destinationId:account.id}:a)}));
  if(JSON.stringify(reactions)!==JSON.stringify(n.reactions)){await n.setReactionsAsync(reactions);redirected++;}
 }
 for(const n of account.findAll(n=>/^Button/.test(n.name))){const label=n.findAll(t=>t.type==='TEXT').map(t=>t.characters).join(' ').trim();if(/^(뒤로\s?가기|이전)$/.test(label))n.visible=false;}
 landing.visible=false;account.visible=true;
 page.flowStartingPoints=[{nodeId:account.id,name:'시작 · 계정 로그인'},...page.flowStartingPoints.filter(p=>p.nodeId!==landing.id&&p.nodeId!==account.id)];
 page.selection=[account];figma.viewport.scrollAndZoomIntoView([account]);
 figma.showUI('<pre id="result"></pre><script>onmessage=e=>result.textContent=JSON.stringify(e.data.pluginMessage,null,2);</script>',{width:480,height:240});
 figma.ui.postMessage({status:'첫 화면 변경 완료',start:page.flowStartingPoints[0],landingVisible:landing.visible,redirected});
})().catch(e=>figma.closePlugin(String(e)));
