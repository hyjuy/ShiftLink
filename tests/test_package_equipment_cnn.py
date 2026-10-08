import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.package_equipment_cnn import package


class EquipmentPackageTests(unittest.TestCase):
    def test_complete_zip_preserves_all_classes_splits_bytes_and_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            cnn,captures,out=root/'cnn',root/'captures',root/'packages'
            rows=[]
            captures.mkdir()
            for kind,split in (('CAU','train'),('CV','test')):
                image=cnn/split/kind/f'{kind}.png'
                image.parent.mkdir(parents=True)
                data=kind.encode()
                image.write_bytes(data)
                row=dict(capture_id=kind,class_name=kind,image=image.relative_to(cnn).as_posix(),
                         sha256=hashlib.sha256(data).hexdigest())
                rows.append(row)
                (captures/f'{kind}.json').write_text(json.dumps({'capture_id':kind}))
            (cnn/'manifest.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            (cnn/'summary.json').write_text('{}')
            (captures/'excluded.png').write_bytes(b'bad')
            (captures/'excluded.json').write_text(json.dumps({'capture_id':'excluded'}))
            (cnn/'excluded.jsonl').write_text(json.dumps({'capture_id':'excluded','reasons':['featureless']})+'\n')
            archives=package(cnn,captures,out)
            self.assertEqual([row['images'] for row in archives],[2])
            with zipfile.ZipFile(out/archives[0]['file']) as archive:
                self.assertEqual(archive.read('train/CAU/CAU.png'),b'CAU')
                self.assertEqual(archive.read('test/CV/CV.png'),b'CV')
                self.assertEqual(json.loads(archive.read('metadata/CV.json')),{'capture_id':'CV'})
                self.assertFalse(any(name.endswith('excluded.png') or name.endswith('/excluded.json') for name in archive.namelist()))
                self.assertIn('dataset-info/excluded.jsonl',archive.namelist())
            self.assertTrue((out/'SHA256SUMS').exists())
            with self.assertRaisesRegex(ValueError,'already exists'):
                package(cnn,captures,out)
