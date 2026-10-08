"""Delete only reviewed excluded photos after validating every copy's hash."""
import argparse
import collections
import hashlib
import json
from pathlib import Path


def retire(excluded, roots):
    if not __debug__:
        raise RuntimeError('hash and path validation requires Python assertions enabled')
    excluded = Path(excluded).resolve()
    rows = [json.loads(line) for line in excluded.read_text(encoding='utf-8').splitlines()]
    rejected = {row['capture_id']: row for row in rows}
    assert len(rejected) == len(rows), 'duplicate exclusion IDs'
    plan, found = [], set()
    for root in map(Path, roots):
        root = root.resolve()
        # Validate writable inventories before deleting a single photograph.
        for inventory in (root / 'dataset/manifest.jsonl', root / 'cnn/manifest.jsonl', root / 'summary.json'):
            if not inventory.exists():
                continue
            assert inventory.resolve() == inventory.absolute() and inventory.resolve().is_relative_to(root)
            if inventory.suffix == '.jsonl':
                parsed = [json.loads(line) for line in inventory.read_text(encoding='utf-8').splitlines()]
                assert all('capture_id' in row for row in parsed)
                if inventory.parent.name == 'cnn':
                    assert all({'split','class_name','target_equipment_id'} <= row.keys() for row in parsed)
            else:
                assert isinstance(json.loads(inventory.read_text(encoding='utf-8')), dict)
                assert (root / 'cnn/manifest.jsonl').is_file()
        log = excluded.parent / 'retirement-result.json'
        assert log.resolve() == log.absolute()
        for folder in ('captures', 'dataset/images', 'cnn'):
            for image in (root / folder).rglob('*.png'):
                if image.stem not in rejected:
                    continue
                assert image.resolve() == image.absolute() and image.resolve().is_relative_to(root)
                assert hashlib.sha256(image.read_bytes()).hexdigest() == rejected[image.stem]['sha256'], image
                found.add(image.stem)
                plan.append(image)
                metadata = image.with_suffix('.json')
                if metadata.exists():
                    assert json.loads(metadata.read_text(encoding='utf-8-sig'))['capture_id'] == image.stem
                    assert metadata.resolve() == metadata.absolute()
                    plan.append(metadata)
                label = root / 'dataset/labels' / image.parent.name / (image.stem + '.txt')
                if folder == 'dataset/images' and label.exists():
                    assert label.resolve() == label.absolute() and label.resolve().is_relative_to(root)
                    plan.append(label)
    assert found == set(rejected), ('missing excluded originals', sorted(set(rejected) - found))
    # Complete validation precedes the first unlink, so a mismatching copy aborts safely.
    paths = sorted(set(plan))
    for path in paths:
        path.unlink()
    for root in map(Path, roots):
        for manifest in (root / 'dataset/manifest.jsonl', root / 'cnn/manifest.jsonl'):
            if manifest.exists():
                records = [json.loads(line) for line in manifest.read_text(encoding='utf-8').splitlines()]
                manifest.write_text(''.join(json.dumps(row) + '\n' for row in records
                                           if row['capture_id'] not in rejected), encoding='utf-8')
        summary_path = root / 'summary.json'
        if summary_path.exists():
            summary = json.loads(summary_path.read_text(encoding='utf-8'))
            retained = [json.loads(line) for line in (root / 'cnn/manifest.jsonl').read_text(encoding='utf-8').splitlines()]
            summary['captured_images'] = summary.get('images', len(retained))
            summary['images'] = summary['unique_images'] = len(retained)
            summary['splits'] = dict(collections.Counter(row['split'] for row in retained))
            summary['captured_equipment'] = summary.get('equipment', {})
            summary['equipment'] = dict(collections.Counter(row['target_equipment_id'] for row in retained))
            summary['shot_kinds'] = dict(collections.Counter(row.get('shot_kind', 'whole') for row in retained))
            counts = collections.defaultdict(collections.Counter)
            directions = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
            for row in retained:
                counts[row['split']][row['class_name']] += 1
                if 'direction_sector' in row:
                    directions[row['target_equipment_id']][row['split']][row['direction_sector']] += 1
            summary['cnn_counts'] = counts
            summary['directions'] = directions
            summary['excluded_photos_retired'] = summary['captured_images'] - len(retained)
            if 'original_images_preserved' in summary:
                summary['original_images_verified_before_curation'] = summary.pop('original_images_preserved')
            summary_path.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    result = dict(excluded_images=len(rejected), deleted_files=len(paths),
                  deleted_paths=[str(path.resolve()) for path in paths], roots=[str(Path(root).resolve()) for root in roots])
    (excluded.parent / 'retirement-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--excluded', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    assert args.excluded.resolve().is_relative_to(workspace)
    roots = [workspace / 'artifacts' / ('equipment-dataset-20261008' + suffix)
             for suffix in ('', '-extra', '-combined')]
    assert all(root.resolve().is_relative_to(workspace) and root.is_dir() for root in roots)
    result = retire(args.excluded, roots)
    print(json.dumps({key: value for key, value in result.items() if key != 'deleted_paths'}, indent=2))
