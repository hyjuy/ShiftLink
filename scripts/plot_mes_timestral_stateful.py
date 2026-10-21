"""Draw saved stateful confirmation metrics, delays, and a fixed alarm trace."""
import argparse
import json
import math
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
    result=json.loads(args.result.read_text(encoding='utf-8'))
    args.out_dir.mkdir(parents=True,exist_ok=False)
    preserving='preserved_hybrid' in result['metrics']
    names=(['ewma','original_hybrid','preserved_hybrid'] if preserving else
           ['ewma','previous_hybrid','stateful','ewma_stateful_ablation'])
    labels=(['EWMA','Original\nhybrid','Preserved\nhybrid'] if preserving else
            ['EWMA','Previous\nhybrid','Stateful\nhybrid','EWMA stateful\n(no Timestral)'])
    colors=['#52677a','#c48b33','#327d6f','#83567b'][:len(names)]
    diagnostic='original_hybrid' if preserving else 'previous_hybrid'
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    for ax,field,title in zip(axes.flat,('injected_event_recall','wrong_alert_equipment_seconds',
            'duplicate_alert_episodes','p95_onset_delay_seconds'),
            ('Weak-fault recall (%)','Wrong-alert equipment-seconds','Duplicate alert starts','Detection delay p95 (s)')):
        values=[result['metrics'][name][field]*(100 if field=='injected_event_recall' else 1) for name in names]
        ax.bar(labels,values,color=colors);ax.set_title(title)
        ax.spines[['top','right']].set_visible(False)
        for i,value in enumerate(values):ax.text(i,value,f'{value:.1f}',ha='center',va='bottom')
        ax.margins(y=.18)
    fig.suptitle('Fresh synthetic confirmation | CPU 1 thread, worker 1, batch 1\nFixed checkpoint and causal alarm state; not Raspberry Pi hardware timing')
    fig.savefig(args.out_dir/'confirmation.png',dpi=160);plt.close(fig)
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root/'output/mes-diagnostic-runtime-20261021'))
    from scripts.mes_validation_candidate_review import load_train_validation
    from scripts.mes_ewma_release_review import event_starts
    _,splits=load_train_validation(args.fresh,profile='independent')
    runs=splits['validation'];del splits['train'];del splits
    alerts={name:{(r,int(s)):set(v) for r,s,v in result['alerts'][name]} for name in names}
    delays={name:sorted(v['delay_seconds'] for v in event_starts(runs,alerts[name]).values() if v['delay_seconds'] is not None) for name in names}
    fig,ax=plt.subplots(figsize=(9,5),layout='constrained')
    for name,label,color in zip(names,labels,colors):
        values=delays[name];metrics=result['metrics'][name]
        assert len(values)==metrics['detected_events']
        assert values[math.ceil(.95*len(values))-1]==metrics['p95_onset_delay_seconds']
        ax.step(values,np.arange(1,len(values)+1)/len(values),where='post',color=color,
            label=f'{label.replace(chr(10)," ")}: {len(values)}/{metrics["injected_events"]}')
        ax.axvline(metrics['p95_onset_delay_seconds'],color=color,ls=':',alpha=.5)
    ax.axhline(.95,color='#888888',ls='--')
    ax.set(xlabel='Seconds from observable onset',ylabel='Cumulative share of detected events',
        title='Detection delay CDF: missed events excluded; vertical dotted lines = p95')
    ax.legend();fig.savefig(args.out_dir/'delay-cdf.png',dpi=160);plt.close(fig)
    counts={}
    for r,rows in runs.items():
        before=set()
        for f,_ in rows:
            current=alerts[diagnostic][(r,f['sequence'])]
            for eq in current-before:counts[(r,eq)]=counts.get((r,eq),0)+1
            before=current
    r,eq=min(counts,key=lambda key:(-counts[key],key))
    rows=runs[r];sequence=[f['sequence'] for f,_ in rows]
    fig,axes=plt.subplots(4,1,figsize=(12,7),sharex=True,layout='constrained')
    for ax,name,label,color in zip(axes[:3],names[:3],labels[:3],colors[:3]):
        ax.step(sequence,[int(eq in alerts[name][(r,s)]) for s in sequence],where='post',color=color)
        ax.set(ylabel=label.replace('\n',' '),ylim=(-.1,1.2))
    axes[0].set_title(f'Most original-hybrid alert starts: {r[:10]} / {eq} (fixed diagnostic selection)')
    axes[3].step(sequence,[int(any(fault['equipment_id']==eq and fault['intensity']>0 for fault in label['faults'])) for _,label in rows],where='post',color='#83567b')
    axes[3].set(ylabel='Active source',xlabel='Sequence (1-second frames)',ylim=(-.1,1.2))
    fig.savefig(args.out_dir/'alarm-trace.png',dpi=160);plt.close(fig)
    summary={'delays':delays,'trace_run':r,'trace_equipment':eq,'selection':f'most {diagnostic} starts; lexical ties'}
    (args.out_dir/'plot-data.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(args.out_dir)


if __name__=='__main__':main()
