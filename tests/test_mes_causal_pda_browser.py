"""Real Chromium DOM regression on Pi, with isolated synthetic UI data only."""
from html import unescape
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
from tempfile import TemporaryDirectory
import unittest

ROOT=Path(__file__).resolve().parents[1]


class PiAlarmBrowserTests(unittest.TestCase):
    def test_same_panel_dedup_acknowledgement_and_no_ai_vibration(self):
        chromium=shutil.which('chromium')
        if not chromium:self.skipTest('Pi Chromium is required')
        source=(ROOT/'shiftlink/mes/web/pda.js').read_text()
        prefix=source[:source.index("\nif (typeof document !== 'undefined') {")]
        start=source.index('const WATCH_MS =')
        functions=source[start:source.index("document.addEventListener('click'",start)]
        page=(ROOT/'shiftlink/mes/web/pda.html').read_text()
        page=re.sub(r'<script\b[^>]*>[\s\S]*?</script>','',page,flags=re.I)
        page=re.sub(r'<link\b[^>]*>','',page,flags=re.I)
        assertions=r'''
const check=(v,m)=>{if(!v)throw Error(m);};
var vibrations=0,picks=[];haptic=()=>vibrations++;notifyBubble=()=>{};openAlertGo=p=>picks.push(p);
S.equipment=['A','B'].map((id,i)=>({equipment_id:id,code:'RT-0'+(i+1),signals:[{signal:'current',name:'모터 전류'}]}));
const snap={run_id:'r',config_id:'c',sequence:10,equipment:[],measurements:[],active_alarms:[{equipment_id:'A',label:'기존 경보'}],
 ai_insights:{status:'ready',run_id:'r',config_id:'c',sequence:10,operational_notifications:false,
 items:['A','B','B'].map(id=>({equipment_id:id,event_id:'r:5:'+id,state:'recent',sequence:5,signals:[{signal:'current',direction:'high'}]}))}};
const panel=$('notifyPanel');panel.hidden=false;
const draw=()=>{S.snapshot=snap;renderAlert(faultsFrom(snap));renderNotifyPanel();};
const rows=()=>[...panel.querySelectorAll('.np-row')];
const operations=()=>JSON.stringify([S.faults,S.alertAck,S.alertUn,vibrations]);
draw();check(rows().length===2,'same equipment duplicated');check(S.alertUn===1,'AI changed alarm badge');
check(rows()[0].textContent.includes('기존 경보')&&rows()[0].textContent.includes('AI 이상징후'),'missing merged evidence');
const first=rows()[0];draw();check(rows()[0]===first,'unchanged poll recreated buttons');
panel.querySelector('.np-all').click();check(Object.keys(S.alertAck).join()==='A','AI acknowledged existing alarm incorrectly');
const before=operations();snap.ai_insights.items[0].event_id='r:10:A';snap.ai_insights.items[0].signals[0].direction='low';
draw();check(operations()===before,'AI re-vibrated or changed existing acknowledgement');check(rows()[0].textContent.includes('낮은'),'AI update stale');
rows()[1].querySelector('.np-go').click();check(picks[0].equipment_id==='B','wrong equipment navigation');check(operations()===before,'AI navigation changed another alarm');
panel.hidden=false;snap.ai_insights.status='stale';draw();check(rows().length===1&&!rows()[0].textContent.includes('AI 이상징후'),'stale AI not removed');
snap.ai_insights.status='ready';snap.active_alarms=[];draw();check(rows().length===2&&S.alertUn===0&&panel.querySelector('.np-all').disabled,'AI-only alarm semantics changed');
snap.ai_insights.run_id='other';draw();check(rows().length===0,'wrong run AI shown');
S.snapshot=null;renderNotifyPanel();check(panel.textContent.includes('확인할 수 없습니다'),'offline AI appears healthy');
snap.ai_insights.run_id='r';snap.active_alarms=[{equipment_id:'A',label:'기존 경보'}];draw();
const stopBefore=operations();snap.line_mode='fault';snap.equipment=[{equipment_id:'A',operating_state:'stopped'}];
snap.ai_insights.status='stopped';snap.ai_insights.items=[{equipment_id:'A',event_id:'r:10:A',sequence:10,state:'before_stop',observed_at:'2026-01-01T00:00:09Z',stop_sequence:10,stopped_at:'2026-01-01T00:00:10Z',signals:[]}];
draw();check(rows().length===1&&rows()[0].textContent.includes('정지 전 감지'),'pre-stop evidence missing or duplicate');
check(operations()===stopBefore,'stop retention re-vibrated or changed acknowledgement');
const held=rows()[0];draw();check(rows()[0]===held,'same stop poll recreated row');
snap.ai_insights.status='stale';draw();check(!panel.textContent.includes('정지 전 감지'),'stale retained evidence shown');
snap.ai_insights.status='ready';snap.line_mode='running';snap.equipment=[];snap.ai_insights.items=['A','B'].map(id=>({equipment_id:id,event_id:'r:5:'+id,state:'recent',sequence:5,signals:[]}));draw();
const rects=rows().map(r=>r.querySelector('.np-go').getBoundingClientRect());
check(rects.every(r=>r.width>=44&&r.height>=44),'small touch target');
check(Math.abs(rects[0].right-rects[1].right)<1,'buttons not aligned');
check(rows().every(r=>r.getBoundingClientRect().right<=panel.getBoundingClientRect().right+1),'alarm row overflow');
document.getElementById('test-result').textContent='ALARM_PANEL_PASS '+JSON.stringify({rows:rows().length,vibrations,buttons:rects.map(r=>({width:r.width,height:r.height,right:r.right}))});
'''
        setup="<pre id='test-result' style='position:fixed;bottom:0;left:0;z-index:10000;font-size:10px;background:white'>NOT_RUN</pre>"
        trap="<script>window.onerror=(m)=>document.getElementById('test-result').textContent='FAIL '+m;</script>"
        script='<script>try{'+prefix+'\n'+functions+'\n'+assertions+"}catch(e){document.getElementById('test-result').textContent='FAIL '+e.stack;}</script>"
        page=page.replace('</body>',setup+trap+script+'</body>')
        with TemporaryDirectory(prefix='shiftlink-browser-') as directory:
            evidence=Path(os.environ.get('SHIFTLINK_BROWSER_EVIDENCE',directory));evidence.mkdir(parents=True,exist_ok=True)
            fixture=Path(directory)/'fixture.html';fixture.write_text(page)
            cmd=[chromium,'--headless','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-extensions',
                 '--user-data-dir='+directory+'/profile','--window-size=430,900','--virtual-time-budget=1500','--dump-dom','--screenshot='+str(evidence/'alarm-panel.png'),
                 fixture.as_uri()]
            proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
            try:stdout,stderr=proc.communicate(timeout=45)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGTERM);stdout,stderr=proc.communicate(timeout=5)
                (evidence/'timeout.out').write_text(stdout);(evidence/'timeout.err').write_text(stderr)
                self.fail('isolated Chromium timeout')
            (evidence/'dom.html').write_text(stdout);(evidence/'chromium.log').write_text(stderr)
            match=re.search(r'<pre id="test-result"[^>]*>([^<]*)</pre>',stdout)
            message=unescape(match.group(1)) if match else 'missing browser test result'
            (evidence/'result.json').write_text(json.dumps(dict(exit_code=proc.returncode,result=message),ensure_ascii=False,indent=2))
            self.assertEqual(proc.returncode,0,stderr[-1500:]);self.assertTrue(message.startswith('ALARM_PANEL_PASS'),message)


if __name__=='__main__':unittest.main()
