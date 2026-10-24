"""Pi Chromium integration check; isolated MES, temporary browser profile, no operating controls."""
import base64
import json
import os
import signal
from importlib.util import find_spec
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

from shiftlink.mes.server import MesService, _Handler

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(Path('/usr/bin/chromium').is_file() and find_spec('websocket'), 'Pi Chromium/CDP environment required')
class RandomModeBrowserTests(unittest.TestCase):
    def test_buttons_and_pda_repair_steps(self):
        import websocket
        service=MesService(ROOT/'docs/data/reference/00_plant_and_relations.json', progressive_faults=True, seed=31,run_nonce='browser')
        handler=type('BrowserHandler',(_Handler,),dict(service=service,web_root=ROOT/'shiftlink/mes/web',api_only=False))
        server=ThreadingHTTPServer(('127.0.0.1',0),handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(service.storage.close)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        temporary=tempfile.TemporaryDirectory(prefix='shiftlink-random-browser-', ignore_cleanup_errors=True)
        self.addCleanup(temporary.cleanup)
        profile=Path(temporary.name)
        error=(profile/'stderr.log').open('w');self.addCleanup(error.close)
        chrome=subprocess.Popen(['/usr/bin/chromium','--headless','--disable-gpu','--no-sandbox',
            '--password-store=basic','--no-first-run','--no-default-browser-check','--remote-allow-origins=*',
            '--remote-debugging-port=0','--user-data-dir='+str(profile),f'http://127.0.0.1:{server.server_port}/'],stdout=error,stderr=error,start_new_session=True)
        def stop():
            os.killpg(chrome.pid,signal.SIGTERM)
            try:chrome.wait(timeout=10)
            except subprocess.TimeoutExpired:chrome.kill();chrome.wait()
        self.addCleanup(stop)
        deadline=time.monotonic()+35
        while not (profile/'DevToolsActivePort').exists():
            if chrome.poll() is not None or time.monotonic()>deadline: self.fail('Chromium did not start')
            time.sleep(.2)
        port=(profile/'DevToolsActivePort').read_text().splitlines()[0]
        with urlopen('http://127.0.0.1:'+port+'/json/list',timeout=5) as r:targets=json.load(r)
        ws=websocket.create_connection(next(t['webSocketDebuggerUrl'] for t in targets if t['type']=='page'),timeout=15)
        self.addCleanup(ws.close)
        counter=0
        def cdp(method,params=None):
            nonlocal counter
            counter+=1;ident=counter
            ws.send(json.dumps(dict(id=ident,method=method,params=params or {})))
            while True:
                result=json.loads(ws.recv())
                if result.get('id')==ident:
                    self.assertNotIn('error',result)
                    return result.get('result',{})
        def js(expression):
            result=cdp('Runtime.evaluate',dict(expression=expression,returnByValue=True,awaitPromise=True))
            self.assertNotIn('exceptionDetails',result,result)
            return result.get('result',{}).get('value')
        def wait(expression):
            end=time.monotonic()+15
            while time.monotonic()<end:
                if js(expression):return
                time.sleep(.2)
            self.fail('Browser condition: '+expression)
        wait("!!document.getElementById('random-toggle')?.onclick && document.getElementById('run-state').dataset.mode === 'stopped' && !document.getElementById('random-toggle').disabled")
        self.assertEqual(js("document.getElementById('random-toggle').getAttribute('aria-pressed')"),'false')
        js("document.getElementById('run-toggle').click()")
        wait("document.getElementById('run-toggle').dataset.command === 'pause'")
        self.assertEqual(service.state()['simulation_mode'],'standard')
        service.engine.tick(430)
        self.assertIsNone(service.engine.scheduler.active)
        js("document.getElementById('random-toggle').click()")
        wait("document.getElementById('random-toggle').getAttribute('aria-pressed') === 'true'")
        service.engine.scheduler.next_fault=1
        service.engine.tick(145)
        equipment_id=service.engine.scheduler.active['equipment_id']
        js("document.querySelector('button[data-equipment="+equipment_id+"]').click()")
        wait("!!document.querySelector('#recovery-panel [data-action=verify]')")
        self.assertTrue(js("document.querySelector('#control-panel [data-command=recover]').disabled"))
        # Run the unchanged PDA's actual step logic against the real resolution API.
        src=(ROOT/'shiftlink/mes/web/pda.js').read_text()
        js("globalThis.pdaSteps=(new Function('module','document',"+json.dumps(src+';return module.exports;')+"))({exports:{}},undefined)")
        equipment_id=service.engine.scheduler.active['equipment_id']
        for cards in ([],['K-1002']):
            out=service.resolution_start(dict(equipment_id=equipment_id,card_ids=cards))
            js('globalThis.repairState='+json.dumps(dict(actions=out['action_suggestions'],steps=[])))
            chips=js('pdaSteps.actionChips(repairState).filter(a=>a.mes)')
            self.assertEqual(len(chips),2)
            self.assertFalse(chips[0]['disabled'])
            self.assertTrue(chips[1]['disabled'])
            js('repairState.steps=[{action:'+json.dumps(chips[0]['text'])+",mes_linked:'recovery_action:verify'}]")
            self.assertFalse(js('pdaSteps.actionChips(repairState).filter(a=>a.mes)[1].disabled'))
        js("document.querySelector('#recovery-panel [data-action=verify]').click()")
        wait("!document.querySelector('#control-panel [data-command=recover]').disabled")
        self.assertIsNone(service.engine.scheduler.active)
        self.assertEqual(service.state()['recovery']['stage'],'ready')
        self.assertEqual(service.state()['line_mode'],'paused')
        js("document.querySelector('#control-panel [data-command=recover]').click()")
        wait("document.getElementById('run-toggle').dataset.command === 'pause'")
        service.engine.tick(4)
        wait("document.querySelector('#recovery-panel').textContent.includes('정상 복귀 완료')")
        # Existing visual controls wrap using their established CSS at both widths.
        evidence=ROOT/'output/random-mode-browser';evidence.mkdir(parents=True,exist_ok=True)
        for width,height in ((1440,900),(390,844)):
            cdp('Emulation.setDeviceMetricsOverride',dict(width=width,height=height,deviceScaleFactor=1,mobile=False))
            js("document.getElementById('simulation-controls').scrollIntoView({block:'start'})")
            time.sleep(.3)
            rects=js("['run-toggle','random-toggle'].map(id=>{const b=document.getElementById(id),r=b.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}})")
            a,b=rects
            for r in rects:
                self.assertGreaterEqual(r['x'],0)
                self.assertGreaterEqual(r['y'],0)
                self.assertLessEqual(r['x']+r['w'],width)
            self.assertTrue(a['x']+a['w']<=b['x']+.5 or a['y']+a['h']<=b['y']+.5)
            shot=cdp('Page.captureScreenshot',dict(format='png',captureBeyondViewport=False))
            (evidence/f'mes-{width}.png').write_bytes(base64.b64decode(shot['data']))
        js("document.getElementById('random-toggle').click()")
        wait("document.getElementById('random-toggle').getAttribute('aria-pressed') === 'false'")
        self.assertEqual(service.state()['simulation_mode'],'standard')
        (evidence/'result.json').write_text(json.dumps(dict(passed=True,pi=True,widths=[1440,390],card_paths=2)))

if __name__=='__main__':unittest.main()
