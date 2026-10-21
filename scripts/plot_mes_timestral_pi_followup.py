"""Plot saved development/confirmation results; never select a model here."""
import argparse
import json
import sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result',type=Path,required=True)
    parser.add_argument('--fresh',type=Path,required=True)
    parser.add_argument('--out-dir',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    result=json.loads(args.result.read_text(encoding='utf-8'))
    args.out_dir.mkdir(parents=True,exist_ok=False)
    names=['ewma','finetuned_default','candidate']
    labels=['EWMA','Timestral FT','EWMA + Timestral']
    colors=['#52677a','#c48b33','#327d6f']
    fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
    for ax,field,title in zip(axes.flat,('injected_event_recall','wrong_alert_equipment_seconds',
            'duplicate_alert_episodes','p95_onset_delay_seconds'),
            ('Weak-fault recall (%)','Wrong-alert equipment-seconds','Duplicate alert starts','Detection delay p95 (s)')):
        y=[result['metrics'][name][field]*(100 if field=='injected_event_recall' else 1) for name in names]
        ax.bar(labels,y,color=colors)
        ax.set_title(title);ax.spines[['top','right']].set_visible(False)
        for x,value in enumerate(y):ax.text(x,value,f'{value:.1f}',ha='center',va='bottom')
        ax.margins(y=.18)
    fig.suptitle('Untouched synthetic confirmation | CPU 1 thread, 1 worker, batch 1\nRecall and false alarms are separate from duplicates and delay')
    fig.savefig(args.out_dir/'confirmation.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,5),layout='constrained')
    for dirname,label,marker,color in (
        ('mes-timestral-pi-followup-development-20261021','Timestral only','o',colors[1]),
        ('mes-timestral-pi-hybrid-development-20261021','Hybrid','^',colors[2])):
        dev=json.loads((root/'output'/dirname/'result.json').read_text(encoding='utf-8'))
        ax.scatter([r['metrics']['wrong_alert_equipment_seconds'] for r in dev['grid']],
                   [100*r['metrics']['injected_event_recall'] for r in dev['grid']],label=label,marker=marker,c=color)
    ax.axvline(19,color=colors[0],ls='--');ax.axhline(100*29/35,color=colors[0],ls='--',label='Development EWMA')
    ax.set(xlabel='Wrong-alert equipment-seconds',ylabel='Weak-fault recall (%)',title='Development only: 36 candidates, 35 reused fault events')
    ax.legend();fig.savefig(args.out_dir/'development.png',dpi=160);plt.close(fig)
    runtime=root/'output/mes-diagnostic-runtime-20261021'
    sys.path.insert(0,str(runtime))
    from scripts.mes_validation_candidate_review import load_train_validation
    from scripts.mes_ewma_release_review import event_starts
    _,splits=load_train_validation(args.fresh,profile='independent')
    runs=splits['validation'];del splits['train'];del splits
    alerts={name:{(r,int(s)):set(v) for r,s,v in result['alerts'][name]} for name in names}
    delays={name:sorted(v['delay_seconds'] for v in event_starts(runs,alerts[name]).values() if v['delay_seconds'] is not None) for name in names}
    fig,ax=plt.subplots(figsize=(8,5),layout='constrained')
    for name,label,color in zip(names,labels,colors):
        values=delays[name]
        ax.step(values,np.arange(1,len(values)+1)/len(values),where='post',color=color,
                label=f'{label}: detected {len(values)}/{result["metrics"][name]["injected_events"]}')
        ax.axvline(result['metrics'][name]['p95_onset_delay_seconds'],color=color,ls=':',alpha=.6)
    ax.axhline(.95,color='#888888',ls='--')
    ax.set(xlabel='Seconds from observable fault onset',ylabel='Cumulative share of detected events',
           title='Detection delay distribution (missed events excluded)')
    ax.legend();fig.savefig(args.out_dir/'delay-cdf.png',dpi=160);plt.close(fig)
    # Fixed diagnostic choice: run/equipment with the most candidate alert starts.
    counts={}
    for r,rows in runs.items():
        previous=set()
        for f,_ in rows:
            current=alerts['candidate'][(r,f['sequence'])]
            for eq in current-previous:counts[(r,eq)]=counts.get((r,eq),0)+1
            previous=current
    r,eq=min(counts,key=lambda key:(-counts[key],key))
    rows=runs[r];sequence=[f['sequence'] for f,_ in rows]
    with np.load(args.result.parent/'confirmation-predictions.npz',allow_pickle=False) as cache:
        equipment=sorted({str(c[0]) for c in cache['channels']})
        idx=equipment.index(eq)
        score={(str(a),int(b)):float(value[idx]) for (a,b),value in zip(cache['context_keys'],cache['equipment_scores'])}
    fig,axes=plt.subplots(4,1,figsize=(12,7),sharex=True,layout='constrained')
    ratio=[score.get((r,s),float('nan'))/result['thresholds'][eq] for s in sequence]
    axes[0].plot(sequence,ratio,color=colors[1]);axes[0].axhline(.1,color=colors[0],ls=':');axes[0].axhline(1.5,color=colors[2],ls='--')
    axes[0].set(ylabel='TS / threshold',title=f'Most candidate alert starts: {r[:10]} / {eq} (diagnostic example)')
    for ax,name,label,color in zip(axes[1:3],('ewma','candidate'),('EWMA alert','Hybrid alert'),(colors[0],colors[2])):
        ax.step(sequence,[int(eq in alerts[name][(r,s)]) for s in sequence],where='post',color=color)
        ax.set(ylabel=label,ylim=(-.1,1.2))
    axes[3].step(sequence,[int(any(fault['equipment_id']==eq and fault['intensity']>0 for fault in label['faults'])) for _,label in rows],where='post',color='#7e4c69')
    axes[3].set(ylabel='Active source',xlabel='Sequence (1-second frames)',ylim=(-.1,1.2))
    fig.savefig(args.out_dir/'alarm-trace.png',dpi=160);plt.close(fig)
    summary={'delay_seconds':delays,'diagnostic_run':r,'diagnostic_equipment':eq,'trace_selection':'most candidate alert starts; lexicographic ties'}
    (args.out_dir/'plot-data.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(args.out_dir)


if __name__=='__main__':main()
