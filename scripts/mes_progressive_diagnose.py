"""Read-only error tracing; preserves the fixed qualification model and inputs."""
from pathlib import Path
import argparse,gzip,json,sys,hashlib
from datetime import datetime,timedelta
from tempfile import TemporaryDirectory
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
ROOT=Path('/home/pi/shiftlink/analytics/validation/mes-progressive-20261024/source')
REL=Path('/home/pi/shiftlink/analytics/releases/active-advisory-v1-pda-20261024-r6')
sys.path.insert(0,str(ROOT));sys.path.insert(1,str(REL))
import scripts;scripts.__path__=[str(REL/'scripts')]
import shiftlink.pda;shiftlink.pda.__path__=['/home/pi/shiftlink/app/shiftlink/pda']
from scripts.mes_causal_active_advisory import ActiveAdvisorySource,ActiveAdvisorySession
from shiftlink.mes.progressive_factory import ProgressiveFactoryEngine
from shiftlink.mes.configuration import from_payload
from shiftlink.mes.contracts import Run
load=lambda p:json.loads(p.read_text())
lock=load(a.out/'candidate-lock.json')
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==s for p,s in lock['files'].items())
result=load(a.out/'result.json');manifest=load(a.out/'manifest.json');config=load(REL/'deploy/analytics/source-config.json')
binding=ActiveAdvisorySource(load(REL/'docs/research/evidence/mes-causal-v14c-20261023/settings.json'),config,load(REL/'deploy/analytics/normal-profile.json'))
specs={(e['equipment_id'],s['signal']):s for e in config['equipment'] for s in e['signals']};codes={e['equipment_id']:e['code'] for e in config['equipment']};out=[]
with TemporaryDirectory(prefix='progressive-diagnostic-') as temp:
 for row in result['cases']:
  if not row.get('unmatched',0) and not row.get('false_notifications',0):continue
  extra=[n for n in row['notices'] if row['kind']=='normal' or n['equipment_id']!=row['equipment_id'] or not row['begin']<=n['sequence']<=row['repair']]
  seqs={n['sequence'] for n in extra};meta=next(c for c in manifest['cases'] if c['id']==row['id'])
  with gzip.open(a.out/'data'/(row['id']+'.json.gz'),'rt') as z:frames=json.load(z)
  session=ActiveAdvisorySession(binding,Path(temp)/(row['id']+'.json'));session.defer_flush=True
  for f in frames[:max(seqs)]:
   if row['kind']!='normal' and f['sequence']==row['repair']+1:
    paused=load(a.out/'private'/(row['id']+'.json'))['paused'];session.sync_stop(paused)
    if session.detector.warm:session.detector._restart();session.notices.clear();session.flush()
   emitted=session.feed(f,binding.config_id)
   if f['sequence'] not in seqs:continue
   for n in [n for n in extra if n['sequence']==f['sequence']]:
    eq=n['equipment_id'];assert eq in emitted;d=session.detector;k=d.equipment.index(eq);features=[]
    measurements={(m['equipment_id'],m['signal']):m for m in f['measurements']}
    for category,mask in [('process',d.episode_process[k]),('flat',d.episode_flat[k])]:
     for j in np.flatnonzero(mask):
      if j>=len(d.channels):features.append({'category':category,'thermal_feature':int(j)});continue
      channel=tuple(d.channels[j]);m=measurements[channel];spec=specs[channel];window=np.asarray(d.flat)[-d.flat_windows[j]:,j]
      features.append(dict(category=category,equipment=channel[0],signal=channel[1],value=m['value'],quality=m['quality'],min=spec['normal_min'],max=spec['normal_max'],normal=spec['normal_min']<=m['value']<=spec['normal_max'],flat_window=d.flat_windows[j],recent_peak_to_peak=float(np.nanmax(window)-np.nanmin(window)),flat_tolerance=float(d.tolerance[j]),known_plateau_bounds=d.plateau_bounds[j]))
    out.append(dict(case=row['id'],sequence=f['sequence'],equipment_id=eq,equipment_code=codes[eq],features=features))
  # Disable faults with the same seed/nonce: normal dynamics have a separate RNG.
  start=datetime.fromisoformat(frames[0]['simulated_at'])-timedelta(seconds=1)
  engine=ProgressiveFactoryEngine(Run.create(meta['seed'],start,config['config_id']),from_payload(config),run_nonce=meta['nonce']);engine.scheduler.next_fault=10**12;engine.start()
  for tick in range(1,max(seqs)+1):
   if row['kind']!='normal' and tick==row['repair']+1:engine.pause();engine.resume()
   snap=engine.tick()
   if tick not in seqs:continue
   for item in [x for x in out if x['case']==row['id'] and x['sequence']==tick]:
    eq=item['equipment_id'];expected=sorted((m['signal'],m['value'],m['quality']) for m in frames[tick-1]['measurements'] if m['equipment_id']==eq);observed=sorted((m.signal,m.value,m.quality) for m in snap.measurements if m.equipment_id==eq)
    item['same_as_fault_disabled']=expected==observed
(a.out/'diagnostic.json').write_text(json.dumps({'events':out,'no_model_changes':True},indent=2));print(json.dumps(out,ensure_ascii=False))