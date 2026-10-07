"""Validate completed Unity PNG/JSON pairs and export a leakage-safe YOLO dataset.

python -m shiftlink.vision.unity_dataset --captures captures --out dataset
"""
import argparse
import hashlib
import json
import math
import re
import shutil
import struct
import zlib
from pathlib import Path

from shiftlink.vision import CLASSES


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def png_dimensions(data):
    require(data[:8] == b'\x89PNG\r\n\x1a\n', 'invalid PNG signature')
    offset, chunks = 8, []
    while offset + 12 <= len(data):
        size = struct.unpack('>I', data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 8 + size
        require(end + 4 <= len(data), 'incomplete PNG chunk')
        body = data[offset + 8:end]
        require(zlib.crc32(kind + body) == struct.unpack('>I', data[end:end + 4])[0], 'PNG CRC mismatch')
        chunks.append((kind, body))
        offset = end + 4
        if kind == b'IEND':
            break
    require(offset == len(data) and chunks and chunks[-1] == (b'IEND', b''), 'incomplete PNG')
    require(chunks[0][0] == b'IHDR' and len(chunks[0][1]) == 13, 'invalid PNG IHDR')
    width, height, depth, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', chunks[0][1])
    require(width > 0 and height > 0 and depth == 8 and color in (0, 2, 4, 6)
            and compression == filtering == interlace == 0, 'unsupported PNG header')
    require(sum(k == b'IHDR' for k, _ in chunks) == 1, 'duplicate PNG IHDR')
    compressed = b''.join(body for kind, body in chunks if kind == b'IDAT')
    require(bool(compressed), 'missing PNG IDAT')
    stride = width * {0: 1, 2: 3, 4: 2, 6: 4}[color] + 1
    inflater = zlib.decompressobj()
    try:
        raw = inflater.decompress(compressed, stride * height + 1)
    except zlib.error as error:
        raise ValueError('invalid PNG IDAT') from error
    require(inflater.eof and not inflater.unused_data and len(raw) == stride * height,
            'invalid PNG pixel data length')
    require(all(raw[i] <= 4 for i in range(0, len(raw), stride)), 'invalid PNG filter')
    return width, height


def validate(metadata, image):
    require(isinstance(metadata, dict), 'metadata must be an object')
    require(type(metadata.get('schema_version')) is int and metadata['schema_version'] == 1, 'unknown schema_version')
    for key in ('capture_id', 'scene_id', 'session_id'):
        require(isinstance(metadata.get(key), str) and metadata[key].strip(), f'missing {key}')
    require(re.fullmatch(r'[A-Za-z0-9_-]+', metadata['capture_id']) is not None, 'unsafe capture_id')
    require(type(metadata.get('seed')) is int, 'seed must be integer')
    width, height = png_dimensions(image)
    require(type(metadata.get('image_width')) is int and type(metadata.get('image_height')) is int
            and (metadata['image_width'], metadata['image_height']) == (width, height), 'PNG dimensions mismatch')
    pose = metadata.get('camera_pose')
    require(isinstance(pose, dict) and bool(pose), 'missing camera_pose')
    # Unity JsonUtility may serialize vectors as arrays or x/y/z objects.
    def valid_pose(value):
        if isinstance(value, dict):
            return bool(value) and all(valid_pose(v) for v in value.values())
        if isinstance(value, list):
            return bool(value) and all(valid_pose(v) for v in value)
        return finite(value)
    require(valid_pose(pose), 'camera_pose must contain finite numeric values')
    require(isinstance(metadata.get('objects'), list), 'missing objects')
    labels = []
    for obj in metadata['objects']:
        require(isinstance(obj, dict), 'invalid object')
        class_id = obj.get('class_id')
        require(type(class_id) is int and 0 <= class_id < len(CLASSES), 'unknown class_id')
        require(obj.get('equipment_type') == CLASSES[class_id], 'class mapping mismatch')
        require(isinstance(obj.get('equipment_id'), str) and obj['equipment_id'].strip(), 'missing equipment_id')
        box = obj.get('bbox_xyxy')
        require(isinstance(box, list) and len(box) == 4 and all(finite(v) for v in box), 'invalid bbox')
        x1, y1, x2, y2 = box
        require(0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height, 'bbox outside image or empty')
        normalized = ((x1 + x2) / (2 * width), (y1 + y2) / (2 * height), (x2 - x1) / width, (y2 - y1) / height)
        labels.append(str(class_id) + ' ' + ' '.join(f'{n:.10g}' for n in normalized))
    return '\n'.join(labels) + ('\n' if labels else '')


def export_dataset(captures, out):
    captures, out = Path(captures).resolve(), Path(out).resolve()
    require(captures.is_dir(), 'captures directory missing')
    require(not out.exists(), 'output already exists; choose a new directory')
    require(not out.is_relative_to(captures), 'output must be outside captures')
    images = sorted(captures.rglob('*.png'))
    sidecars = sorted(captures.rglob('*.json'))
    require(images, 'no PNG captures')
    require({p.with_suffix('') for p in images} == {p.with_suffix('') for p in sidecars}, 'incomplete PNG/JSON pairs')
    records, ids = [], set()
    for image_path in images:
        try:
            metadata = json.loads(image_path.with_suffix('.json').read_text(encoding='utf-8-sig'))
        except (ValueError, UnicodeError) as error:
            raise ValueError(f'invalid JSON: {image_path.with_suffix(".json")}') from error
        image = image_path.read_bytes()
        label = validate(metadata, image)
        capture_id = metadata['capture_id']
        require(capture_id not in ids, 'duplicate capture_id')
        ids.add(capture_id)
        records.append(dict(metadata=metadata, source=image_path, label=label, sha256=hashlib.sha256(image).hexdigest()))

    # Merge shared scenes, sessions and identical images before assigning a split.
    parents = list(range(len(records)))
    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    seen = {}
    for i, record in enumerate(records):
        for key in (('scene', record['metadata']['scene_id']), ('session', record['metadata']['session_id']), ('hash', record['sha256'])):
            if key in seen:
                parents[root(i)] = root(seen[key])
            seen[key] = i
    members = {}
    for i, record in enumerate(records):
        members.setdefault(root(i), []).append(record['metadata']['capture_id'])
    groups = {i: hashlib.sha256(json.dumps(sorted(names)).encode()).hexdigest() for i, names in members.items()}
    rows = []
    for i, record in enumerate(records):
        group = groups[root(i)]
        bucket = int(group, 16) % 100
        split = 'train' if bucket < 70 else 'val' if bucket < 85 else 'test'
        capture_id = record['metadata']['capture_id']
        rows.append(dict(schema_version=1, capture_id=capture_id, image=f'images/{split}/{capture_id}.png',
                         label=f'labels/{split}/{capture_id}.txt', sha256=record['sha256'], group=group, split=split,
                         scene_id=record['metadata']['scene_id'], session_id=record['metadata']['session_id'], seed=record['metadata']['seed']))
    out.mkdir(parents=True)
    for split in ('train', 'val', 'test'):
        (out / 'images' / split).mkdir(parents=True)
        (out / 'labels' / split).mkdir(parents=True)
    for row, record in zip(rows, records):
        shutil.copyfile(record['source'], out / row['image'])
        (out / row['label']).write_text(record['label'], encoding='utf-8')
    (out / 'manifest.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
    (out / 'data.yaml').write_text('path: ' + json.dumps(out.as_posix()) + '\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n'
                                  + ''.join(f'  {i}: {name}\n' for i, name in enumerate(CLASSES)), encoding='utf-8')
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--captures', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    try:
        rows = export_dataset(args.captures, args.out)
    except (ValueError, OSError) as error:
        parser.exit(1, f'error: {error}\n')
    counts = {split: sum(row['split'] == split for row in rows) for split in ('train', 'val', 'test')}
    print(json.dumps(counts))
    if not all(counts.values()):
        print('WARNING: empty split; collect additional independent scenes/sessions before training/evaluation.')


if __name__ == '__main__':
    main()
