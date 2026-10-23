"""New paired runs with declared bad-sample stress; existing A/B physics unchanged."""
import hashlib
import json
from pathlib import Path
import random
from urllib.request import Request,urlopen
from scripts import mes_causal_data as d
from scripts import mes_causal_v9 as prior
from scripts.mes_causal_schema import signals,MANUAL

ROLES={'development':(7,1024),'test':(7,1024)}


def identity(role,family,index):
    seed=1201000+list(ROLES).index(role)*1000+(family=='B')*100+index
    return f'causal-v12-{role}-{family}-{seed}',seed


def generate(path,role,lock=None):
    if role=='test':prior.require_lock(lock)
    path=Path(path);path.mkdir(parents=True,exist_ok=False)
    ledger,entries={},[];count,ticks=ROLES[role];specs=signals()
    with d.local_mes() as server,(path/'features.jsonl').open('x',encoding='utf-8') as target:
        base='http://127.0.0.1:'+str(server.server_address[1])
        def post(route,payload):
            with urlopen(Request(base+route,json.dumps(payload).encode(),method='POST'),timeout=30) as response:return json.load(response)
        for family in ('A','B'):
            for index in range(count):
                group,seed=identity(role,family,index);rng=random.Random(seed+37);events=[]
                if index:
                    drive='EQ-0004' if index%2 else 'EQ-0005';utility='EQ-0001' if index%2 else 'EQ-0003'
                    sensor=[('EQ-0002','bus_voltage'),('EQ-0006','rt_motor_current'),('EQ-0007','rt_vib_rms'),
                            ('EQ-0008','rt_clamp_press'),('EQ-0009','cv_motor_current')][(index-1)%5]
                    kinds=[('friction' if index%2 else 'cooling_loss',drive,None),
                           ('leak' if index%2 else 'blockage',utility,None),('sensor_stuck',*sensor)]
                    for i,((kind,eq,sig),start) in enumerate(zip(kinds,(100,230,370))):
                        at=start+rng.randint(-12,12)
                        duration=rng.randint(48,64) if kind=='sensor_stuck' else rng.randint(32,60)
                        events.append(dict(event_id=str(i),kind=kind,equipment=eq,signal=sig,start=at,
                                           end=at+duration,amplitude=rng.uniform(.5,2.5)))
                start=rng.randint(140,180);length=rng.randint(6,14)
                quality=[dict(equipment=e['equipment'],signal=e['signal'],tick=e['start']+25)
                         for e in events if e['kind']=='sensor_stuck']
                for control in ([False,True] if events else [False]):
                    run=hashlib.sha256((group+str(control)).encode()).hexdigest()[:32]
                    intervention=[] if control else events;ledger[run]=intervention
                    post('/benchmark/reset',dict(family=family,seed=seed,run_id=run,events=intervention,pauses=False))
                    held={}
                    for tick in range(ticks):
                        frame=post('/benchmark/step',{})
                        for m in frame['measurements']:
                            key=m['equipment_id'],m['signal']
                            if m['signal'] not in MANUAL and m['signal']!='rt_lift_delay' and specs[key]['unit']!='bool':
                                if tick==start-1:held[key]=m['value']
                                if start<=tick<start+length:m['value']=held[key]
                            if any(tick==q['tick'] and key==(q['equipment'],q['signal']) for q in quality):m['quality']='bad'
                        target.write(json.dumps(frame,separators=(',',':'),allow_nan=False)+'\n')
                    entries.append(dict(run_id=run,seed=seed,nonce=group+str(control),group_id=group,family=family,
                                        control=control,frames=ticks,hold=[start,length],quality_stress=quality))
    d.write_new(path/'events.private.json',ledger)
    d.write_new(path/'manifest.json',dict(role=role,runs=entries,features_sha256=d.sha(path/'features.jsonl'),
        ledger_sha256=d.sha(path/'events.private.json'),candidate_lock_sha256=d.sha(lock) if lock else None,
        transport='isolated localhost HTTP',is_synthetic=True,quality_stress='one bad sample at stuck start+25, also in paired control'))
