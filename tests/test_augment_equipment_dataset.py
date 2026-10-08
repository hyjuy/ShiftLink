import json
from pathlib import Path
import tempfile
import unittest

from scripts.augment_equipment_dataset import merge_captures


class AugmentDatasetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        self.old,self.extra,self.out=root/'old',root/'extra',root/'combined'
        for directory,name,split in ((self.old,'old','test'),(self.extra,'extra','train')):
            folder=directory/'CAU-01'/split
            folder.mkdir(parents=True)
            row=dict(capture_id=name,target_equipment_id='EQ-0003',dataset_split=split,
                     camera_pose={'position':[-3,1.5,0]},target_center=[0,1,0])
            (folder/f'{name}.json').write_text(json.dumps(row))
            (folder/f'{name}.png').write_bytes(name.encode())

    def test_preserves_original_bytes_and_split_and_derives_opposite_direction(self):
        self.assertEqual(merge_captures(self.old,self.extra,self.out),2)
        target=self.out/'CAU-01/test/old'
        self.assertEqual(target.with_suffix('.png').read_bytes(),b'old')
        self.assertEqual((self.old/'CAU-01/test/old.png').read_bytes(),b'old')
        row=json.loads(target.with_suffix('.json').read_text())
        self.assertEqual((row['dataset_split'],row['shot_kind'],row['direction_sector']),('test','whole',6))

    def test_rejects_incomplete_pair_before_creating_output(self):
        (self.extra/'CAU-01/train/extra.png').unlink()
        with self.assertRaisesRegex(ValueError,'incomplete'):
            merge_captures(self.old,self.extra,self.out)
        self.assertFalse(self.out.exists())

    def test_rejects_duplicate_id_before_creating_output(self):
        path=self.extra/'CAU-01/train/extra.json'
        row=json.loads(path.read_text())
        row['capture_id']='old'
        path.write_text(json.dumps(row))
        with self.assertRaisesRegex(ValueError,'duplicate'):
            merge_captures(self.old,self.extra,self.out)
        self.assertFalse(self.out.exists())

    def test_refuses_to_overwrite_existing_output(self):
        self.out.mkdir()
        with self.assertRaisesRegex(ValueError,'already exists'):
            merge_captures(self.old,self.extra,self.out)
