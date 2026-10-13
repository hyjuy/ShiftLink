(()=>{
 const svg=content=>'<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+content+'</svg>';
 document.querySelectorAll('.appbar .ic,.bar button').forEach(b=>{
  if(b.textContent.includes('⌂'))b.innerHTML=svg('<path d="m3 10 9-7 9 7v11h-6v-7H9v7H3Z"/>')+'<span>홈</span>';
  else if(b.textContent.trim().startsWith('←'))b.innerHTML=svg('<path d="M20 12H4m6-6-6 6 6 6"/>')+'<span>이전</span>';
 });
 const emptyPages={
  '26-handover-empty':['인계 기록이 없습니다','등록된 인계 기록이 없습니다.'],
  '28-outbox-empty':['업로드 대기가 없습니다','대기 중인 인계는 없습니다.'],
  '29-outbox-error':['대기 목록을 불러오지 못했습니다','MES에 연결한 뒤 다시 확인해 주세요.']
 };
 const emptyScreen=document.querySelector('#s-empty');if(emptyScreen){const footer=emptyScreen.querySelector('.pane'),body=emptyScreen.querySelector('.empty');if(footer&&body&&!footer.contains(body))footer.prepend(body);}
 const wait=document.querySelector('#s-wait .pane');if(wait&&!wait.querySelector('.wait-content')){const progress=wait.querySelector('.steps-prog'),label=wait.querySelector('#waitLbl'),cards=wait.querySelector('#waitCards');if(progress&&label&&cards){const group=document.createElement('div');group.className='wait-content';const safe=document.createElement('div');safe.className='wait-safety';safe.append(label,cards);group.append(progress,safe);wait.prepend(group);}}
 const outbox=document.querySelector('#obPane');if(outbox&&outbox.querySelectorAll('.card').length>2)outbox.classList.add('long-content');
 document.querySelectorAll('.land-main').forEach(main=>{if(main.querySelector('.tf')&&main.querySelectorAll('.card,.try').length<=1)main.classList.add('sparse-content');});
 const id=location.pathname.split('/').pop().replace('.html',''),copy=emptyPages[id];
 if(copy){const pane=document.querySelector('.screen.on .pane');pane.classList.add('empty-state');const notes=Array.from(pane.querySelectorAll('.hint')).map(n=>n.textContent);pane.innerHTML='<div class="state-box"><div class="state-icon">'+svg('<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6m-6 4h6m-6 4h4"/>')+'</div><h2>'+copy[0]+'</h2><p>'+copy[1]+'</p><p class="state-note">'+notes.filter(t=>t!==copy[1]&&!t.includes('대기 중인 인계는')).join('<br>')+'</p></div>';}
})();

if(new URLSearchParams(location.search).has("embed")&&document.getElementById("chat-artboard")){if(document.body.firstElementChild.id!=="chat-artboard")document.body.firstElementChild.remove();document.body.style.cssText="height:800px;min-height:800px;overflow:hidden";document.documentElement.style.cssText="height:800px;overflow:hidden";}
