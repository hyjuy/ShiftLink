from pathlib import Path
import sys,json,gzip,time,subprocess,hashlib,shutil,zipfile
from urllib.request import urlopen
v=Path(__file__).resolve().parent;root=v/'source';sys.path.insert(0,str(root))
from scripts.mes_causal_active_advisory import ActiveAdvisorySource,ActiveAdvisorySession
from shiftlink.pda.ai_insights import read_insights
load=lambda p:json.loads(p.read_text())
b=ActiveAdvisorySource(load(root/'docs/research/evidence/mes-causal-v14c-20261023/settings.json'),load(root/'deploy/analytics/source-config.json'),load(root/'deploy/analytics/normal-profile.json'))
old=v.parent/'fault-lifecycle-20261024';case=next(c for c in load(old/'development/manifest.json')['cases'] if c['id']=='002-hydraulic_leak-intermittent-2');event=case['events'][0];eq=event['equipment_id']
with gzip.open(old/'development/cases'/(case['id']+'.json.gz'),'rt') as f:frames=json.load(f)
folder=v/'trace-final';folder.mkdir(exist_ok=True);session=ActiveAdvisorySession(b,folder/'checkpoint.json');session.defer_flush=True;k=session.detector.equipment.index(eq);rows=[];notices=[];elapsed=[]
for i,frame in enumerate(frames):
 t=time.perf_counter();events=session.feed(frame,b.config_id);value=session.report(frame);elapsed.append(time.perf_counter()-t)
 if eq in events:notices.append(frame['sequence'])
 rows.append(dict(index=i,on=bool(session.detector.episode_on[k]),quiet=int(session.detector.episode_quiet[k]),items=[r for r in value['items'] if r['equipment_id']==eq]))
session.flush();quiet=[r for r in rows[104:event['repair']] if not any(a<=r['index']<z for a,z in event['symptom_segments'])];original=load(old/'gap-trace/summary.json');release=next(r['index'] for r in rows[event['repair']:] if not r['on']);ids={r['items'][0]['event_id'] for r in rows if r['items']}
summary=dict(case=case['id'],frames=len(frames),notices=notices,original_notices=original['notices'],first_release_index=release,original_first_release_index=original['first_release_after_repair_index'],quiet_samples=len(quiet),previous_quiet_hidden=original['quiet_samples_with_hidden_recent_item'],candidate_quiet_hidden=sum(not r['items'] for r in quiet),event_ids=sorted(ids),feed_and_report_p95_ms=1000*sorted(elapsed)[int(.95*(len(elapsed)-1))],scope='consumed synthetic development replay on Pi; compute timing excludes replay wait, network, browser and fsync')
assert notices==original['notices'] and release==original['first_release_after_repair_index'] and len(ids)==1 and summary['candidate_quiet_hidden']==0
(folder/'rows.json').write_text(json.dumps(rows));(v/'display-summary.json').write_text(json.dumps(summary,indent=2));print('DISPLAY',json.dumps(summary),flush=True)
# Exercise only the original read-only GET + stop-switch branch of the selected CLI.
stop=v/'CLI_STOP';stop.touch();profile=root/'deploy/analytics/normal-profile.json'
cmd=[sys.executable,'-m','scripts.mes_causal_active_advisory','--mes-url','http://jetson-06.tail0a6af3.ts.net:8000','--source-config',str(root/'deploy/analytics/source-config.json'),'--normal-profile',str(profile),'--normal-profile-sha256',hashlib.sha256(profile.read_bytes()).hexdigest(),'--settings',str(root/'docs/research/evidence/mes-causal-v14c-20261023/settings.json'),'--state-dir',str(v/'cli-state'),'--output',str(v/'cli-output.json'),'--stop-file',str(stop),'--once']
r=subprocess.run(cmd,cwd=root,capture_output=True,text=True,timeout=30);(v/'cli.log').write_text(r.stdout+r.stderr);assert r.returncode==0;assert load(v/'cli-output.json')['status']=='disabled';print('CLI_STOP_PASS',flush=True)
# Preserve exact operating originals; no writes to app/release paths.
originals=v/'original-sources';originals.mkdir(exist_ok=True)
for name,p in [('operating-reader.py',Path('/home/pi/shiftlink/app/shiftlink/pda/ai_insights.py')),('operating-pda.js',Path('/home/pi/shiftlink/app/shiftlink/mes/web/pda.js')),('worker.py',old/'source/scripts/mes_causal_pda_service.py'),('lifecycle.py',old/'source/scripts/mes_causal_lifecycle.py')]:
 if p.exists():shutil.copy2(p,originals/name)
candidate=v/'candidate'
for relative in ['scripts/mes_causal_active_advisory.py','shiftlink/pda/ai_insights.py','shiftlink/mes/web/pda.js','tests/test_pda_active_display.py','tests/pda_active_advisory.cjs']:
 p=candidate/relative;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/relative,p)
shutil.copy2(root/'js-checks.json',v/'js-checks.json')
pins=load(v/'before-pins.json');changed=[p for p,h in pins.items() if not Path(p).is_file() or hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
service=dict(line.split('=',1) for line in subprocess.check_output(['systemctl','show','shiftlink-analytics.service','-p','MainPID','-p','NRestarts','-p','ActiveState','-p','SubState'],text=True).strip().splitlines())
with urlopen('http://127.0.0.1:8080/api/state',timeout=15) as f:state=json.load(f)
final=dict(changed_operating_pins=changed,checked_pins=len(pins),service=service,previous_main_pid='7066',operating_pid_unchanged=service['MainPID']=='7066',legacy_alarm_count=len(state.get('active_alarms',[])),operating_ai_status=state.get('ai_insights',{}).get('status'),line_mode=state.get('line_mode'),run_id=state.get('run_id'),sequence=state.get('sequence'),temperature_c=float(Path('/sys/class/thermal/thermal_zone0/temp').read_text())/1000,throttling=subprocess.check_output(['vcgencmd','get_throttled'],text=True).strip(),pi_tests_only=True,operating_deployment=False,physical_vibration_measured=False,torch_loaded='torch' in sys.modules,timestral_loaded='timestral' in sys.modules)
(v/'final-integrity.json').write_text(json.dumps(final,indent=2));assert not changed and final['operating_pid_unchanged'] and service['NRestarts']=='0' and service['ActiveState']=='active';print('INTEGRITY',json.dumps(final),flush=True)
with zipfile.ZipFile(v/'evidence-final.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(v.iterdir()):
  if p.is_file() and p.suffix in ('.json','.log','.py'):z.write(p,p.name)
 for folder in ('candidate','original-sources','trace-final'):
  for p in sorted((v/folder).rglob('*')):
   if p.is_file():z.write(p,str(p.relative_to(v)))
with zipfile.ZipFile(v/'evidence-final.zip') as z:assert z.testzip() is None
record=dict(path=str(v/'evidence-final.zip'),sha256=hashlib.sha256((v/'evidence-final.zip').read_bytes()).hexdigest(),bytes=(v/'evidence-final.zip').stat().st_size)
(v/'archive-final.json').write_text(json.dumps(record,indent=2));print('ARCHIVE',json.dumps(record),flush=True)
