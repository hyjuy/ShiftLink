"""Capture handheld equipment views, validate boxes, and export CNN classification folders."""
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shiftlink.vision.unity_dataset import export_dataset
from shiftlink.vision.unity_cls import convert as export_cnn
from check_human_captures import check as check_human_captures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--per-equipment', type=int, default=360)
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--equipment-codes', help='Comma-separated installed equipment codes; default all 10')
    args = parser.parse_args()
    if not args.editor.is_file():
        parser.error('Unity editor missing')
    out = args.out.resolve()
    source = ROOT / 'unity/ShiftLinkFactory'
    project = out / 'unity-job'
    project.mkdir(parents=True, exist_ok=True)
    for directory in ('Scripts', 'Editor', 'Models', 'Resources'):
        shutil.copytree(source / 'Assets' / directory, project / 'Assets' / directory, dirs_exist_ok=True)
        meta = source / 'Assets' / (directory + '.meta')
        if meta.exists():
            shutil.copyfile(meta, project / 'Assets' / meta.name)
    for directory in ('Packages', 'ProjectSettings'):
        shutil.copytree(source / directory, project / directory, dirs_exist_ok=True)
    (project / 'Checks').mkdir(exist_ok=True)
    for name in ('config.json', 'state.json'):
        shutil.copyfile(source / 'Checks' / name, project / 'Checks' / name)
    run = out / 'smoke' if args.smoke else out
    run.mkdir(exist_ok=True)
    captures = run / 'captures'
    result_path = run / 'capture-result.txt'
    result_path.unlink(missing_ok=True)
    command = [str(args.editor), '-batchmode', '-force-d3d11', '-projectPath', str(project),
               '-executeMethod', 'FactoryDatasetCapture.Run', '-logFile', str(run / 'unity-capture.log'),
               '--capture-output', str(captures), '--photos-per-equipment', str(24 if args.smoke else args.per_equipment)]
    if args.equipment_codes:
        command.extend(['--equipment-codes', args.equipment_codes])
    print('Starting ' + ('direction/detail smoke check' if args.smoke else 'additional capture'), flush=True)
    result = subprocess.run(command, cwd=ROOT, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if result.returncode or not result_path.exists():
        raise RuntimeError(f'Unity capture failed ({result.returncode}); see {run / "unity-capture.log"}')
    print(result_path.read_text(), flush=True)
    check_human_captures(captures, 24 if args.smoke else args.per_equipment)
    dataset = run / 'dataset'
    rows = export_dataset(captures, dataset)
    targets = collections.defaultdict(collections.Counter)
    objects = collections.Counter()
    hashes = set()
    for path in captures.rglob('*.json'):
        metadata = json.loads(path.read_text(encoding='utf-8-sig'))
        targets[metadata['target_equipment_id']][metadata['dataset_split']] += 1
        assert any(obj['equipment_id'] == metadata['target_equipment_id'] for obj in metadata['objects']), path
        objects.update(obj['equipment_type'] for obj in metadata['objects'])
    for row in rows:
        if row['sha256'] in hashes:
            raise RuntimeError('Duplicate rendered image: ' + row['capture_id'])
        hashes.add(row['sha256'])
    expected = {'train': 24} if args.smoke else {'train': args.per_equipment * 8 // 10, 'val': args.per_equipment // 10, 'test': args.per_equipment // 10}
    expected_targets = len(args.equipment_codes.split(',')) if args.equipment_codes else 10
    assert len(targets) == expected_targets and all(dict(counts) == expected for counts in targets.values()), dict(targets)
    cnn = run / 'cnn'
    cnn_counts = export_cnn(dataset, cnn, captures=captures)
    summary = dict(images=len(rows), resolution=[1280, 720], equipment=dict(targets),
                   splits=dict(collections.Counter(row['split'] for row in rows)), annotated_objects=dict(objects),
                   unique_images=len(hashes), source='Unity synthetic factory',
                   viewpoint='handheld-first-person', camera_height_m=[1.2, 1.8],
                   layout_spacing=1.5, factory_floor_m=[66, 51],
                   lighting_profiles=['dim', 'normal', 'bright', 'warm', 'cool'],
                   cnn_dataset=cnn.as_posix(), cnn_counts=cnn_counts, cnn_label_policy='target_equipment_id from original metadata; whole photograph',
                   source_asset_sha256={path.relative_to(project).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                                        for directory in ('Models', 'Resources/Factory')
                                        for path in sorted((project / 'Assets' / directory).rglob('*'))
                                        if path.suffix in ('.fbx', '.prefab')},
                   split_policy='all 12 directions in each split; prefer disjoint angular subranges, recorded fallback within sector for blocked poses; scene/session/hash groups cannot cross splits',
                   limitation='same synthetic assets; real-camera generalization has not been measured')
    (run / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
