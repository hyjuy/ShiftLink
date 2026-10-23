"""Pi-only validation of incremental v14c; never installs or touches services.

Reuses an explicitly supplied, preserved measurement harness for GET health,
resource sampling and synthetic-image model calls. All output is create-only.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import time
import unittest
import zipfile


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, indent=2)


def harness(path):
    spec = importlib.util.spec_from_file_location('preserved_measurement', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def regress(args):
    from scripts.mes_causal_v14_stream import OnlineDetector
    source = args.root / 'scripts/mes_causal_v14_stream.py'
    reached = set()
    def tracer(frame, event, arg):
        if frame.f_code.co_filename == str(source):
            if event == 'line': reached.add(frame.f_lineno)
            return tracer
        return None
    suite = unittest.defaultTestLoader.loadTestsFromName('tests.test_mes_causal_v14_stream')
    sys.settrace(tracer)
    with (args.out / 'stream-regression.log').open('x') as f:
        result = unittest.TextTestRunner(stream=f, verbosity=2).run(suite)
    sys.settrace(None)
    import dis
    executable = set()
    def lines(code):
        executable.update(line for _, line in dis.findlinestarts(code) if line)
        for c in code.co_consts:
            if isinstance(c, type(code)): lines(c)
    lines(compile(source.read_text(encoding='utf-8-sig'), str(source), 'exec'))
    # Import/class-definition lines are exercised by importing the module above,
    # before tracing; report them as uncovered, conservatively.
    cov = dict(kind='stdlib line tracing, import lines conservatively uncovered',
               covered=len(reached & executable), executable=len(executable),
               percent=100 * len(reached & executable) / len(executable), missing=sorted(executable - reached))
    save(args.out / 'stream-regression.json', dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors), coverage=cov))
    if not result.wasSuccessful() or cov['percent'] < 80: raise RuntimeError('stream regression/coverage failed')
    tests = unittest.TestSuite(); excluded = []
    def add(suite):
        for t in suite:
            if isinstance(t, unittest.TestSuite): add(t)
            elif 'test_predict_batch_shape_and_future_exclusion' in t.id() or 'tail_guarded' in t.id(): excluded.append(t.id())
            else: tests.addTest(t)
    names = ['test_mes_causal_benchmark', 'test_mes_causal_train', 'test_mes_causal_contract_edges']
    names += [p.stem for p in sorted((args.root / 'tests').glob('test_mes_causal_v*.py')) if 'stream' not in p.stem]
    for name in names:
        if (args.root / 'tests' / (name + '.py')).exists():
            add(unittest.defaultTestLoader.loadTestsFromName('tests.' + name))
    with (args.out / 'existing-regression.log').open('x') as f:
        old = unittest.TextTestRunner(stream=f, verbosity=2).run(tests)
    save(args.out / 'existing-regression.json',dict(tests=old.testsRun, failures=len(old.failures),errors=len(old.errors),excluded=excluded))
    if not old.wasSuccessful(): raise RuntimeError('existing regression failed')
    total = {}
    for name, folder, feature, expected_file in (
        ('development', args.bundle, 'frames.jsonl', 'expected.json'),
        ('consumed_test', args.replay, 'features.jsonl', 'expected.json')):
        settings = load(folder / 'settings.json')
        expected = {(r, t): set(e) for r,t,e in load(folder / expected_file)['v14']}
        if name == 'consumed_test':
            digest = hashlib.sha256((folder / feature).read_bytes()).hexdigest()
            if digest != load(folder / 'manifest.json')['features_sha256']: raise RuntimeError('consumed input hash mismatch')
        detector = OnlineDetector(settings); count=notices=mismatch=0; runs=set(); costs=[]
        with (args.out / (name + '-parity.jsonl')).open('x') as output:
            for line in (folder / feature).open():
                frame=json.loads(line); t=time.monotonic(); actual=detector.step(frame); costs.append(time.monotonic()-t)
                key=frame['run_id'],frame['sequence']; match=actual==expected[key]
                count+=1; notices+=len(actual); mismatch+=not match; runs.add(key[0])
                if actual or not match: output.write(json.dumps(dict(run_id=key[0], sequence=key[1], actual=sorted(actual),expected=sorted(expected[key]),match=match))+'\n')
        if count!=len(expected): raise RuntimeError('frame/key count mismatch')
        total[name]=dict(frames=count,runs=len(runs),notices=notices,mismatches=mismatch,history_sizes=detector.history_sizes,
                         processing_p95=sorted(costs)[math.ceil(.95*len(costs))-1],processing_max=max(costs),
                         scope='consumed synthetic regression; not new unused evaluation')
        if mismatch: raise RuntimeError('row parity mismatch: '+name)
    total['torch_loaded']='torch' in sys.modules;total['timestral_loaded']='timestral' in sys.modules
    save(args.out / 'parity.json',total)
    if total['torch_loaded'] or total['timestral_loaded']:raise RuntimeError('neural runtime loaded')
    print('REGRESSION_PASS',json.dumps(total),flush=True)


def phase(args, probe, name, combined):
    from scripts.mes_causal_v14_stream import OnlineDetector
    out=args.out/name;out.mkdir(exist_ok=False)
    service=probe.discover_pda_pid();detector=OnlineDetector(load(args.bundle/'settings.json'))
    expected={(r,t):set(e) for r,t,e in load(args.bundle/'expected.json')['v14']}
    lines=[];run=None
    for line in (args.bundle/'frames.jsonl').open():
        rid=json.loads(line)['run_id'];run=run or rid
        if rid!=run or len(lines)>=args.frames:break
        lines.append(line)
    if len(lines)!=args.frames:raise RuntimeError('insufficient paced input')
    workers=[];logs=[];resources=[];rows=[];reason=[];produced=[]
    stopped=threading.Event();q=queue.Queue(maxsize=4)
    try:
        if combined:
            for kind in ('face','cnn'):
                f=(out/(kind+'.log')).open('x');logs.append(f)
                workers.append(subprocess.Popen(['/home/pi/shiftlink/venv-face/bin/python','-B',str(Path(__file__).resolve()),'--vision',kind,'--reference-probe',str(args.reference_probe),'--out',str(out)],stdout=f,stderr=subprocess.STDOUT))
            deadline=time.monotonic()+45
            while not all((out/(k+'-ready.json')).exists() for k in ('face','cnn')):
                if any(p.poll() is not None for p in workers) or time.monotonic()>deadline:raise RuntimeError('vision startup failed')
                time.sleep(.25)
        epoch=time.monotonic()+.2
        def producer():
            for i,raw in enumerate(lines):
                due=epoch+i
                if stopped.wait(max(0,due-time.monotonic())):break
                try:q.put_nowait((i,raw,due,time.monotonic()));produced.append(i)
                except queue.Full:reason.append('queue_full');break
        thread=threading.Thread(target=producer,daemon=True);thread.start()
        with (out/'frames.jsonl').open('x') as f:
            while len(rows)<args.frames:
                if (args.out/'STOP').exists():reason.append('stop_marker');break
                if reason:break
                if any(p.poll() is not None for p in workers):reason.append('vision_exit');break
                try:i,raw,due,enqueued=q.get(timeout=2)
                except queue.Empty:reason.append('source_timeout');break
                begin=time.monotonic();frame=json.loads(raw);notice=detector.step(frame);end=time.monotonic()
                row=dict(sequence=i,processing=end-begin,queue_wait=begin-enqueued,schedule_to_done=end-due,
                         queue_size=q.qsize(),deadline_miss=end>due+1,parity=notice==expected[(run,i)],notifications=sorted(notice))
                rows.append(row);f.write(json.dumps(row)+'\n');f.flush()
                if not row['parity']:reason.append('parity');break
                if i%5==0:
                    s=probe.sample([os.getpid(),service]+[p.pid for p in workers]);s['pda']=probe.health();resources.append(s)
                    if s['temp_c']>=75 or s['available_kb']<524288 or s['throttle']!='throttled=0x0':reason.append('resource_guard');break
                    if s['pda'].get('status')!=200 or s['processes'][str(service)].get('exited'):reason.append('pda_guard');break
                if i%60==0:print(name,i,flush=True)
        stopped.set();thread.join(timeout=2)
    finally:
        stopped.set()
        if workers:(out/'STOP_VISION').touch()
        for p in workers:
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=5)
        for f in logs:f.close()
    result=dict(requested=args.frames,produced=len(produced),processed=len(rows),reasons=reason,
                parity_all=all(r['parity'] for r in rows),deadline_misses=sum(r['deadline_miss'] for r in rows),
                processing_p95=probe.p95([r['processing'] for r in rows if r['sequence']>=64]),
                processing_max=max(r['processing'] for r in rows),schedule_to_done_p95=probe.p95([r['schedule_to_done'] for r in rows if r['sequence']>=64]),
                maximum_queue_wait=max(r['queue_wait'] for r in rows),maximum_queue_size=max(r['queue_size'] for r in rows),
                history_sizes=detector.history_sizes,service_pid=service,vision={},
                max_temp_c=max(s['temp_c'] for s in resources),minimum_available_kb=min(s['available_kb'] for s in resources),
                torch_loaded='torch' in sys.modules,timestral_loaded='timestral' in sys.modules,
                scope='1Hz synthetic source parse+incremental analysis with GET health; excludes MES network and PDA alarm rendering')
    for kind,p in zip(('face','cnn'),workers):result['vision'][kind]=dict(exit_code=p.returncode,result=load(out/(kind+'-result.json')))
    result['passed']=len(rows)==args.frames and len(produced)==args.frames and not reason and result['parity_all'] and result['deadline_misses']==0 and all(s['throttle']=='throttled=0x0' for s in resources) and all(v['exit_code']==0 and v['result']['calls']>=args.frames for v in result['vision'].values())
    save(out/'resources.json',resources);save(out/'result.json',result)
    print(name,json.dumps(result),flush=True)
    if not result['passed']:raise RuntimeError(name+' failed')
    return result


def main(args):
    probe=harness(args.reference_probe)
    if args.vision:return probe.vision(args.vision,args.out)
    args.out.mkdir(exist_ok=False)
    probe.verify_bundle(args.bundle)
    before=load(args.bundle.parent/'followup-before.json')
    original={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in before['files']}
    if original!=before['files']:raise RuntimeError('original service files changed before test')
    save(args.out/'preserved-before.json',dict(files=original,pda_pid=probe.discover_pda_pid(),health=probe.health()))
    regress(args)
    phases={}
    for name,combined in [('analysis-only',False),('face-cnn-combined',True)]:
        phases[name]=phase(args,probe,name,combined)
    probe.verify_bundle(args.bundle)
    after={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in original}
    result=dict(phases=phases,service_files_unchanged=original==after,current_pda_pid=probe.discover_pda_pid(),pda_health=probe.health(),
                source_sha256=hashlib.sha256((args.root/'scripts/mes_causal_v14_stream.py').read_bytes()).hexdigest(),
                reference_probe_sha256=hashlib.sha256(args.reference_probe.read_bytes()).hexdigest(),passed=original==after)
    save(args.out/'final.json',result)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path);p.add_argument('--bundle',type=Path);p.add_argument('--replay',type=Path)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--reference-probe',type=Path,required=True)
    p.add_argument('--frames',type=int,default=256);p.add_argument('--vision',choices=['face','cnn']);args=p.parse_args()
    if args.root:sys.path.insert(0,str(args.root))
    main(args)
