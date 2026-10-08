"""Check actual rendered photographs for handheld viewpoints and lighting coverage."""
import argparse
import collections
import json
import math
from pathlib import Path


def check(captures, per_equipment=600):
    groups = collections.defaultdict(list)
    for path in Path(captures).rglob('*.json'):
        row = json.loads(path.read_text(encoding='utf-8-sig'))
        height = row['camera_pose']['position'][1] - row.get('standing_floor_y', 0)
        assert 1.2 <= height <= 1.8, f'{path}: camera height {height} is not handheld'
        assert row.get('viewpoint') == 'handheld-first-person', path
        assert row.get('standpoint_clear') is True, path
        assert row.get('lighting_profile') in ('dim', 'normal', 'bright', 'warm', 'cool'), path
        for key in ('sun_intensity', 'interior_light_intensity'):
            level=row.get(key)
            assert type(level) in (int, float) and math.isfinite(level) and level>0, (path,key)
        ambient=row.get('ambient_rgb')
        assert isinstance(ambient,list) and len(ambient)==3 and all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in ambient), path
        assert any(o['equipment_id'] == row['target_equipment_id'] for o in row['objects']), path
        assert row.get('shot_kind') in ('whole', 'detail'), path
        position=row['camera_pose']['position']
        center=row['target_center']
        angle=math.degrees(math.atan2(position[2]-center[2],position[0]-center[0]))%360
        assert int(angle//30)==row.get('direction_sector'), (path,angle)
        assert abs((angle-row['azimuth_degrees']+180)%360-180)<.1, path
        if row['shot_kind']=='detail':
            assert row.get('feature_name') and row.get('feature_visible') is True, path
        groups[row['target_equipment_id']].append(row)
    assert groups, 'no captures'
    for equipment, rows in groups.items():
        assert len(rows) == per_equipment, (equipment, len(rows))
        if per_equipment in (360,600,960):
            assert collections.Counter(r['dataset_split'] for r in rows) == {'train': per_equipment*8//10, 'val': per_equipment//10, 'test': per_equipment//10}
            expected_detail=300
            assert collections.Counter(r['shot_kind'] for r in rows)=={'whole':per_equipment-expected_detail,'detail':expected_detail}, equipment
            for split in ('train', 'val', 'test'):
                assert set(r['direction_sector'] for r in rows if r['dataset_split']==split)==set(range(12)), (equipment,split,'directions')
                assert set(r['lighting_profile'] for r in rows if r['dataset_split'] == split) == {'dim', 'normal', 'bright', 'warm', 'cool'}
                levels={profile: [r['sun_intensity'] for r in rows if r['dataset_split']==split and r['lighting_profile']==profile]
                        for profile in ('dim','normal','bright')}
                assert max(levels['dim'])<min(levels['normal']) and max(levels['normal'])<min(levels['bright']), (equipment,split,'brightness did not vary')
    return {equipment: len(rows) for equipment, rows in groups.items()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('captures', type=Path)
    parser.add_argument('--per-equipment', type=int, default=600)
    args = parser.parse_args()
    print(json.dumps(check(args.captures, args.per_equipment), indent=2))
