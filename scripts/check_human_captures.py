"""Check actual rendered photographs for handheld viewpoints and lighting coverage."""
import argparse
import collections
import json
from pathlib import Path


def check(captures, per_equipment=600):
    groups = collections.defaultdict(list)
    for path in Path(captures).rglob('*.json'):
        row = json.loads(path.read_text(encoding='utf-8-sig'))
        height = row['camera_pose']['position'][1]
        assert 1.2 <= height <= 1.8, f'{path}: camera height {height} is not handheld'
        assert row.get('viewpoint') == 'handheld-first-person', path
        assert row.get('standpoint_clear') is True, path
        assert row.get('lighting_profile') in ('dim', 'normal', 'bright', 'warm', 'cool'), path
        assert any(o['equipment_id'] == row['target_equipment_id'] for o in row['objects']), path
        groups[row['target_equipment_id']].append(row)
    assert groups, 'no captures'
    for equipment, rows in groups.items():
        assert len(rows) == per_equipment, (equipment, len(rows))
        if per_equipment == 600:
            assert collections.Counter(r['dataset_split'] for r in rows) == {'train': 480, 'val': 60, 'test': 60}
            for split in ('train', 'val', 'test'):
                assert set(r['lighting_profile'] for r in rows if r['dataset_split'] == split) == {'dim', 'normal', 'bright', 'warm', 'cool'}
    return {equipment: len(rows) for equipment, rows in groups.items()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('captures', type=Path)
    parser.add_argument('--per-equipment', type=int, default=600)
    args = parser.parse_args()
    print(json.dumps(check(args.captures, args.per_equipment), indent=2))
