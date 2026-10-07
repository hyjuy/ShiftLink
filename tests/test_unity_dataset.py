"""Unity capture -> YOLO dataset guarantees, using only stdlib fixtures."""
import copy
import json
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

from shiftlink.vision.unity_dataset import export_dataset, png_dimensions


def png(width=100, height=50, color=0):
    def chunk(kind, body):
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress((b'\x00' + bytes([color]) * width * 3) * height)) + chunk(b'IEND', b''))


class UnityDatasetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'captures'
        self.source.mkdir()
        self.out = self.root / 'dataset'

    def capture(self, name='one', color=0, **updates):
        metadata = dict(schema_version=1, capture_id=name, scene_id='scene', session_id='session', seed=1,
                        image_width=100, image_height=50,
                        camera_pose=dict(position=[0, 1, 2], rotation=[0, 0, 0, 1]),
                        objects=[dict(class_id=0, equipment_type='HPU', equipment_id='EQ-0001', bbox_xyxy=[10, 5, 90, 45])])
        metadata.update(updates)
        (self.source / f'{name}.png').write_bytes(png(color=color))
        (self.source / f'{name}.json').write_text(json.dumps(metadata), encoding='utf-8')
        return metadata

    def test_export_normalizes_labels_and_backgrounds_and_manifest(self):
        self.capture()
        self.capture('background', color=1, objects=[])
        rows = export_dataset(self.source, self.out)
        self.assertEqual(len(rows), 2)
        labels = {p.stem: p.read_text() for p in (self.out / 'labels').rglob('*.txt')}
        self.assertEqual(labels['one'], '0 0.5 0.5 0.8 0.8\n')
        self.assertEqual(labels['background'], '')
        self.assertEqual(len({row['split'] for row in rows}), 1)
        self.assertEqual(len((self.out / 'manifest.jsonl').read_text().splitlines()), 2)
        self.assertIn('5: PDP', (self.out / 'data.yaml').read_text())
        self.assertTrue(all((self.out / row['image']).exists() for row in rows))

    def test_invalid_metadata_does_not_create_output(self):
        original = self.capture()
        cases = [dict(schema_version=2), dict(image_width=99), dict(seed=True), dict(camera_pose={}),
                 dict(objects=[dict(class_id=6, equipment_type='NOPE', equipment_id='EQ', bbox_xyxy=[0, 0, 1, 1])])]
        for box in ([0, 0, 0, 1], [-1, 0, 5, 5], [0, 0, 101, 5], [0, 0, float('nan'), 5]):
            obj = copy.deepcopy(original['objects'][0])
            obj['bbox_xyxy'] = box
            cases.append(dict(objects=[obj]))
        for update in cases:
            with self.subTest(update=update):
                (self.source / 'one.json').write_text(json.dumps(original | update))
                with self.assertRaises(ValueError):
                    export_dataset(self.source, self.out)
                self.assertFalse(self.out.exists())

    def test_rejects_incomplete_corrupt_and_duplicate_ids(self):
        self.capture()
        (self.source / 'lost.png').write_bytes(png())
        with self.assertRaises(ValueError):
            export_dataset(self.source, self.out)
        (self.source / 'lost.png').unlink()
        self.capture('two', capture_id='one')
        with self.assertRaises(ValueError):
            export_dataset(self.source, self.out)
        (self.source / 'two.png').unlink()
        (self.source / 'two.json').unlink()
        (self.source / 'one.png').write_bytes(b'not png')
        with self.assertRaises(ValueError):
            export_dataset(self.source, self.out)

    def test_determinism_and_duplicate_split_protection(self):
        for i in range(30):
            self.capture(f'capture{i}', color=i, scene_id=f'scene{i}', session_id=f'session{i}')
        self.capture('duplicate', color=0, scene_id='other', session_id='other')
        rows = export_dataset(self.source, self.out)
        again = export_dataset(self.source, self.root / 'again')
        self.assertEqual(rows, again)
        same_hash = [r for r in rows if r['sha256'] == rows[0]['sha256']]
        self.assertEqual(len({r['split'] for r in same_hash}), 1)
        self.assertEqual({r['split'] for r in rows}, {'train', 'val', 'test'})
        with self.assertRaises(ValueError):
            export_dataset(self.source, self.out)

    def test_cli_and_empty_input(self):
        with self.assertRaises(ValueError):
            export_dataset(self.source, self.out)
        self.capture()
        result = subprocess.run([sys.executable, '-B', '-m', 'shiftlink.vision.unity_dataset', '--captures', str(self.source),
                                 '--out', str(self.out)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('WARNING: empty split', result.stdout)

    def test_recursive_object_pose_and_all_six_classes(self):
        names = ('HPU', 'GR', 'RT', 'CV', 'CAU', 'PDP')
        objects = [dict(class_id=i, equipment_type=name, equipment_id=f'EQ-{i}', bbox_xyxy=[0, 0, 100, 50])
                   for i, name in enumerate(names)]
        self.capture(objects=objects, camera_pose=dict(position=dict(x=1, y=2, z=3), rotation=dict(x=0, y=0, z=0, w=1)))
        nested = self.source / 'nested'
        nested.mkdir()
        for path in list(self.source.glob('one.*')):
            path.rename(nested / path.name)
        rows = export_dataset(self.source, self.out)
        self.assertEqual((self.out / rows[0]['label']).read_text(), ''.join(f'{i} 0.5 0.5 1 1\n' for i in range(6)))

    def test_missing_fields_unknown_class_mapping_and_invalid_json(self):
        original = self.capture()
        for key in original:
            metadata = original.copy()
            del metadata[key]
            with self.subTest(key=key):
                (self.source / 'one.json').write_text(json.dumps(metadata))
                with self.assertRaises(ValueError):
                    export_dataset(self.source, self.out)
        for update in (dict(capture_id='../escape'), dict(camera_pose={'x': float('inf')}), dict(objects=[{}]),
                       dict(objects=[original['objects'][0] | dict(equipment_type='GR')])):
            (self.source / 'one.json').write_text(json.dumps(original | update))
            with self.assertRaises(ValueError):
                export_dataset(self.source, self.out)
        (self.source / 'one.json').write_text('{broken')
        with self.assertRaises(ValueError):
            export_dataset(self.source, self.out)

    def test_png_corruption_and_nested_output_rejected(self):
        good = png()
        corrupt_crc = bytearray(good)
        corrupt_crc[29] ^= 1
        for image in (bytes(corrupt_crc), good[:-5], good + b'extra'):
            with self.assertRaises(ValueError):
                png_dimensions(image)
        self.capture()
        with self.assertRaises(ValueError):
            export_dataset(self.source, self.source / 'export')


if __name__ == '__main__':
    unittest.main()
