"""Preserve existing photographs and combine validated additional camera captures."""
import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.check_human_captures import check
from shiftlink.vision.unity_dataset import export_dataset
from shiftlink.vision.unity_cls import convert


def merge_captures(existing, additional, out):
    existing,additional,out=map(Path,(existing,additional,out))
    if out.exists():
        raise ValueError('output already exists')
    centers={}
    records=[]
    ids=set()
    for source in (additional,existing):
        images=set(source.rglob('*.png'))
        metadata=set(source.rglob('*.json'))
        if not images or {p.with_suffix('') for p in images}!={p.with_suffix('') for p in metadata}:
            raise ValueError('incomplete capture pairs')
        for path in sorted(metadata):
            row=json.loads(path.read_text(encoding='utf-8-sig'))
            if row['capture_id'] in ids:
                raise ValueError('duplicate capture_id')
            ids.add(row['capture_id'])
            equipment=row['target_equipment_id']
            if source==additional:
                centers[equipment]=row['target_center']
            else:
                center=centers[equipment]
                position=row['camera_pose']['position']
                angle=math.degrees(math.atan2(position[2]-center[2],position[0]-center[0]))%360
                row.update(shot_kind='whole',feature_name='',feature_visible=False,
                           target_center=center,azimuth_degrees=angle,direction_sector=int(angle//30))
            records.append((path,row,path.relative_to(source)))
    for path,row,relative in records:
        target=out/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf-8')
        shutil.copy2(path.with_suffix('.png'),target.with_suffix('.png'))
    return len(records)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--existing',type=Path,required=True)
    parser.add_argument('--additional',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():
        parser.error('output already exists; sources are preserved')
    old=json.loads((args.existing/'summary.json').read_text(encoding='utf-8'))
    extra=json.loads((args.additional/'summary.json').read_text(encoding='utf-8'))
    assert old['images']==6000 and extra['images']==3600
    for name,digest in old['source_asset_sha256'].items():
        if name.endswith('.fbx'):
            assert extra['source_asset_sha256'][name]==digest, ('model changed',name)
    check(args.additional/'captures',360)
    captures=args.out/'captures'
    assert merge_captures(args.existing/'captures',args.additional/'captures',captures)==9600
    equipment=check(captures,960)
    dataset=args.out/'dataset'
    rows=export_dataset(captures,dataset)
    assert len(rows)==len({r['sha256'] for r in rows})==9600
    original=[json.loads(line) for line in (args.existing/'dataset/manifest.jsonl').read_text(encoding='utf-8').splitlines()]
    hashes={r['capture_id']:r['sha256'] for r in rows}
    assert all(hashes[r['capture_id']]==r['sha256'] for r in original), 'original photographs changed'
    cnn=args.out/'cnn'
    counts=convert(dataset,cnn,captures=captures)
    metadata={}
    for path in captures.rglob('*.json'):
        row=json.loads(path.read_text(encoding='utf-8-sig'))
        metadata[row['capture_id']]=row
    manifest=[]
    directions=collections.defaultdict(lambda:collections.defaultdict(collections.Counter))
    features=collections.defaultdict(collections.Counter)
    for row in rows:
        meta=metadata[row['capture_id']]
        kind=next(obj['equipment_type'] for obj in meta['objects'] if obj['equipment_id']==meta['target_equipment_id'])
        image=f"{row['split']}/{kind}/{row['capture_id']}.png"
        assert hashlib.sha256((cnn/image).read_bytes()).hexdigest()==row['sha256']
        directions[meta['target_equipment_id']][row['split']][meta['direction_sector']]+=1
        if meta['shot_kind']=='detail':
            features[meta['target_equipment_id']][meta['feature_name']]+=1
        manifest.append(dict(row,image=image,class_name=kind,target_equipment_id=meta['target_equipment_id'],
                             shot_kind=meta['shot_kind'],direction_sector=meta['direction_sector'],feature_name=meta['feature_name']))
    (cnn/'manifest.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in manifest),encoding='utf-8')
    summary=dict(images=9600,unique_images=9600,original_images_preserved=6000,additional_images=3600,
                 equipment=equipment,splits=dict(collections.Counter(r['split'] for r in rows)),
                 shot_kinds=dict(collections.Counter(r['shot_kind'] for r in metadata.values())),
                 directions=directions,features=features,cnn_counts=counts,resolution=[1280,720],
                 source_asset_sha256=extra['source_asset_sha256'],
                 original_source=args.existing.as_posix(),additional_source=args.additional.as_posix(),
                 cnn_label_policy='target_equipment_id; full photograph without post-capture crop',
                 limitation='synthetic factory; real-camera generalization and model accuracy not measured')
    (args.out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS: 9600 unique photographs; all 6000 original PNG bytes preserved; CNN labels verified',flush=True)


if __name__=='__main__':
    main()
