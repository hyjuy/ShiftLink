"""Select readable CNN photos using heuristics and explicit visual review."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import shutil


def quality_reasons(metadata,mean_luma,std_luma,visual_keep=False):
    if visual_keep:
        return []
    target=next(obj for obj in metadata['objects'] if obj['equipment_id']==metadata['target_equipment_id'])
    area=lambda obj:(obj['bbox_xyxy'][2]-obj['bbox_xyxy'][0])*(obj['bbox_xyxy'][3]-obj['bbox_xyxy'][1])
    target_area=area(target)
    reasons=[]
    minimum=.12 if metadata['shot_kind']=='detail' else .08
    if target_area<metadata['image_width']*metadata['image_height']*minimum:
        reasons.append('small_target')
    if any(obj['equipment_type']!=target['equipment_type'] and area(obj)>target_area*1.2 for obj in metadata['objects']):
        reasons.append('dominant_other_class')
    # Low-light photographs remain useful when visible structure retains contrast.
    if mean_luma<8 and std_luma<8:
        reasons.append('too_dark')
    if std_luma<8:
        reasons.append('low_contrast')
    if metadata['shot_kind']=='detail' and not (metadata.get('feature_name') and metadata.get('feature_visible')):
        reasons.append('hidden_or_missing_feature')
    return reasons


def main():
    from PIL import Image,ImageStat
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--review-exclusions',type=Path,required=True)
    parser.add_argument('--review-keeps',type=Path)
    args=parser.parse_args()
    if args.out.exists():
        parser.error('output already exists; candidate photos are preserved')
    reviewed={row['capture_id']:row['reason'] for row in json.loads(args.review_exclusions.read_text(encoding='utf-8'))}
    keeps={} if args.review_keeps is None else {row['capture_id']:row['reason'] for row in json.loads(args.review_keeps.read_text(encoding='utf-8'))}
    if set(keeps)&set(reviewed):
        parser.error('conflicting keep and exclude review IDs')
    metadata={}
    for path in (args.source/'captures').rglob('*.json'):
        row=json.loads(path.read_text(encoding='utf-8-sig'))
        metadata[row['capture_id']]=row
    unknown=(set(reviewed)|set(keeps))-set(metadata)
    if unknown:
        parser.error('review exclusions contain unknown capture IDs: '+str(sorted(unknown)))
    manifest=[json.loads(line) for line in (args.source/'cnn/manifest.jsonl').read_text(encoding='utf-8').splitlines()]
    kept,rejected=[],[]
    counts=collections.defaultdict(collections.Counter)
    equipment=collections.defaultdict(collections.Counter)
    directions=collections.defaultdict(lambda:collections.defaultdict(collections.Counter))
    lighting=collections.defaultdict(collections.Counter)
    for row in manifest:
        meta=metadata[row['capture_id']]
        target=next(obj for obj in meta['objects'] if obj['equipment_id']==meta['target_equipment_id'])
        image=args.source/'cnn'/row['image']
        with Image.open(image) as photo:
            stats=ImageStat.Stat(photo.crop(tuple(target['bbox_xyxy'])).convert('L'))
        reasons=quality_reasons(meta,stats.mean[0],stats.stddev[0],row['capture_id'] in keeps)
        if row['capture_id'] in reviewed:
            reasons.append('review: '+reviewed[row['capture_id']])
        record=dict(row,mean_target_luma=stats.mean[0],std_target_luma=stats.stddev[0])
        if row['capture_id'] in keeps:
            record['visual_keep_reason']=keeps[row['capture_id']]
        if reasons:
            rejected.append(dict(record,reasons=reasons))
            continue
        kept.append(record)
        counts[row['split']][row['class_name']]+=1
        equipment[meta['target_equipment_id']][row['split']]+=1
        directions[meta['target_equipment_id']][row['split']][meta['direction_sector']]+=1
        lighting[meta['lighting_profile']][row['split']]+=1
    for split in ('train','val','test'):
        assert set(counts[split])=={'HPU','PDP','CAU','GR','RT','CV'}, (split,counts[split])
    for row in kept:
        target=args.out/row['image']
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(args.source/'cnn'/row['image'],target)
        assert hashlib.sha256(target.read_bytes()).hexdigest()==row['sha256'], target
    (args.out/'manifest.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in kept),encoding='utf-8')
    (args.out/'excluded.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rejected),encoding='utf-8')
    summary=dict(candidate_images=len(manifest),retained_images=len(kept),excluded_images=len(rejected),
                 splits=dict(collections.Counter(row['split'] for row in kept)),cnn_counts=counts,
                 equipment=equipment,directions=directions,lighting=lighting,
                 shot_kinds=dict(collections.Counter(row['shot_kind'] for row in kept)),
                 exclusion_reasons=dict(collections.Counter(reason for row in rejected for reason in row['reasons'])),
                 criteria={'whole_target_area_min':.08,'detail_target_area_min':.12,'other_class_area_max_ratio':1.2,
                           'near_black_luma_and_std_max_255':8,'target_luma_std_min_255':8},
                 reviewer_exclusions=args.review_exclusions.as_posix(),candidate_source=args.source.as_posix(),
                 reviewer_keeps=keeps,
                 limitation='heuristic quality filter plus sampled visual review; model accuracy not measured')
    (args.out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':
    main()
