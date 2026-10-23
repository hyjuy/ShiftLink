"""Pi-only normal-context regression, observed replay, and paced vision load."""
import argparse,dis,hashlib,json,math,os,subprocess,sys,time,unittest
from pathlib import Path
from scripts.mes_causal_context import ContextDetector
from scripts.mes_causal_context_run import read,load,save,sha
from scripts.mes_causal_v14_stream import OnlineDetector
from scripts.mes_causal_pda_service import BoundSource
from scripts.mes_causal_v14_stream_validate import harness
ROOT=Path(__file__).resolve().parents[1]
SETTINGS=ROOT/'docs/research/evidence/mes-causal-v14c-20261023/settings.json'


def regression(out,profile):
    names=['tests.test_mes_causal_context','tests.test_mes_causal_context_service','tests.test_mes_causal_v14_stream','tests.test_mes_causal_pda_service','tests.test_pda_advisory_reader','tests.test_pda_fault_stop','tests.test_analytics_release']
    sources=[ROOT/p for p in ('scripts/mes_causal_context.py','scripts/mes_causal_pda_service.py','shiftlink/pda/ai_insights.py')];reached={str(p):set() for p in sources}
    def trace(frame,event,arg):
        if frame.f_code.co_filename in reached:
            if event=='line':reached[frame.f_code.co_filename].add(frame.f_lineno)
            return trace
    suite=unittest.defaultTestLoader.loadTestsFromNames(names);sys.settrace(trace)
    with (out/'tests.log').open('x') as file:result=unittest.TextTestRunner(stream=file,verbosity=2).run(suite)
    sys.settrace(None);coverage={}
    for p in sources:
        executable=set()
        def lines(code):
            executable.update(n for _,n in dis.findlinestarts(code) if n)
            for c in code.co_consts:
                if isinstance(c,type(code)):lines(c)
        lines(compile(p.read_text(encoding='utf-8-sig'),str(p),'exec'));hit=reached[str(p)]&executable
        coverage[str(p.relative_to(ROOT))]=dict(covered=len(hit),executable=len(executable),percent=100*len(hit)/len(executable),missing=sorted(executable-hit))
    save(out/'tests.json',dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),coverage=coverage,scope='conservative stdlib executable line trace; import lines excluded from reached'))
    assert result.wasSuccessful() and all(v['percent']>=80 for v in coverage.values())
    parity={}
    for name,folder,feature in [('development',Path('/tmp/shiftlink-v14c-test.eOqMDX/bundle'),'frames.jsonl'),('consumed-test',Path('/tmp/shiftlink-v14c-test.eOqMDX/stream-runtime-v1/consumed-replay'),'features.jsonl')]:
        settings=load(folder/'settings.json');expected={(r,t):set(e) for r,t,e in load(folder/'expected.json')['v14']};d=ContextDetector(settings,profile);count=notices=bad=0
        before=sha(folder/feature)
        for f in read(folder/feature):
            actual=d.step(f);count+=1;notices+=len(actual);bad+=actual!=expected[f['run_id'],f['sequence']]
        parity[name]=dict(frames=count,notices=notices,mismatches=bad,input_sha256=before,unchanged=before==sha(folder/feature));assert count==len(expected) and not bad and parity[name]['unchanged']
    save(out/'parity.json',parity);print('REGRESSION',result.testsRun,coverage,parity,flush=True)


def observed(out,profile,source):
    settings=load(SETTINGS);binding=BoundSource(settings,load(ROOT/'deploy/analytics/source-config.json'),normal_profile=profile)
    models=dict(original=OnlineDetector(settings),candidate=binding.new_detector())
    for d in models.values():d.config_id=binding.config_id
    notices={n:[] for n in models};normal={n:[] for n in models};count=0
    for frame in read(source):
        adapted=binding.adapt(frame,binding.config_id);count+=1
        for name,d in models.items():
            events=d.step(adapted)
            for eq in events:
                row=dict(sequence=frame['sequence'],equipment_id=eq);notices[name].append(row)
                e=next(e for e in frame['equipment'] if e['equipment_id']==eq)
                if frame['line_mode']=='running' and e['operating_state']=='running' and e.get('fault_level')=='normal' and not any(a.get('equipment_id')==eq for a in frame.get('active_alarms',[])):normal[name].append(row)
    result=dict(frames=count,notices=notices,normal_notices=normal,scope='previously consumed synthetic operating diagnostic; normal flags used only for retrospective scoring',passed=not normal['candidate'])
    save(out/'observed.json',result);print('OBSERVED',json.dumps(result),flush=True);assert result['passed']


def paced(out,profile,source,probe_path,frames):
    probe=harness(probe_path);settings=load(SETTINGS);data=[];rid=None
    for f in read(source):
        rid=rid or f['run_id']
        if f['run_id']!=rid or len(data)==frames:break
        data.append(f)
    assert len(data)==frames
    d=ContextDetector(settings,profile);d.config_id=profile['source_config_id'];expected=[d.step(f) for f in data]
    d=ContextDetector(settings,profile);d.config_id=profile['source_config_id'];old=probe.discover_pda_pid();workers=[];logs=[];resources=[];timings=[];failures=[]
    try:
        for kind in ('face','cnn'):
            log=(out/(kind+'.log')).open('x');logs.append(log)
            workers.append(subprocess.Popen(['/home/pi/shiftlink/venv-face/bin/python','-B',str(ROOT/'scripts/mes_causal_v14_stream_validate.py'),'--vision',kind,'--reference-probe',str(probe_path),'--out',str(out)],stdout=log,stderr=subprocess.STDOUT))
        deadline=time.monotonic()+60
        while not all((out/(k+'-ready.json')).exists() for k in ('face','cnn')):
            assert all(p.poll() is None for p in workers) and time.monotonic()<deadline,'vision initialization'
            time.sleep(.25)
        epoch=time.monotonic()+.2
        for i,f in enumerate(data):
            due=epoch+i;time.sleep(max(0,due-time.monotonic()));begin=time.monotonic();actual=d.step(f);end=time.monotonic()
            timings.append(dict(sequence=f['sequence'],seconds=end-begin,scheduled_seconds=end-due,parity=actual==expected[i],deadline_miss=end>due+1))
            if actual!=expected[i] or end>due+1:failures.append('timing_or_parity');break
            if i%5==0:
                r=probe.sample([os.getpid(),old]+[p.pid for p in workers]);r['health']=probe.health();resources.append(r)
                if r['temp_c']>=75 or r['available_kb']<524288 or r['throttle']!='throttled=0x0' or r['health'].get('status')!=200 or probe.discover_pda_pid()!=old:failures.append('resource_or_pda');break
            if any(p.poll() is not None for p in workers):failures.append('vision_exit');break
            if i%60==0:print('PACED',i,flush=True)
    finally:
        (out/'STOP_VISION').touch()
        for p in workers:
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=5)
        for log in logs:log.close()
    vision={k:dict(exit_code=p.returncode,result=load(out/(k+'-result.json'))) for k,p in zip(('face','cnn'),workers)}
    result=dict(requested=frames,processed=len(timings),failures=failures,processing_p95=probe.p95([r['seconds'] for r in timings]),processing_max=max(r['seconds'] for r in timings),scheduled_p95=probe.p95([r['scheduled_seconds'] for r in timings]),deadline_misses=sum(r['deadline_miss'] for r in timings),max_temp_c=max(r['temp_c'] for r in resources),min_available_kb=min(r['available_kb'] for r in resources),throttling=sorted(set(r['throttle'] for r in resources)),pda_pid_preserved=probe.discover_pda_pid()==old,vision=vision,torch_loaded='torch' in sys.modules,timestral_loaded='timestral' in sys.modules,scope='1Hz approved-config synthetic replay plus face/CNN synthetic-image inference; excludes MES network/UI display')
    result['passed']=len(timings)==frames and not failures and all(v['exit_code']==0 and v['result']['calls']>=frames for v in vision.values())
    save(out/'paced.json',result);save(out/'resources.json',resources);save(out/'timings.json',timings);print('PACED_RESULT',json.dumps(result),flush=True);assert result['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=('regression','observed','paced'),required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--profile',type=Path,required=True);p.add_argument('--source',type=Path);p.add_argument('--frames',type=int,default=192);p.add_argument('--probe',type=Path,default=Path('/tmp/shiftlink-v14c-test.eOqMDX/followup-probe.py'));a=p.parse_args();a.out.mkdir(exist_ok=False);profile=load(a.profile)
    if a.phase=='regression':regression(a.out,profile)
    elif a.phase=='observed':observed(a.out,profile,a.source)
    else:paced(a.out,profile,a.source,a.probe,a.frames)
