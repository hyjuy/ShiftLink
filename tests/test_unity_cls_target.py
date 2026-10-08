"""CNN whole-photo labels follow the intended photographed equipment."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from shiftlink.vision.unity_cls import convert


class TargetClassTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.dataset=self.root/'dataset'
        self.captures=self.root/'captures'
        self.captures.mkdir()
        self.out=self.root/'cnn'

    def photo(self, split='train', target='EQ-0001', equipment_type='HPU'):
        name='photo-'+split
        image=self.dataset/'images'/split/(name+'.png')
        image.parent.mkdir(parents=True,exist_ok=True)
        image.write_bytes(b'unchanged whole-photograph bytes')
        label=self.dataset/'labels'/split/(name+'.txt')
        label.parent.mkdir(parents=True,exist_ok=True)
        label.write_text('0 0.5 0.5 0.2 0.2\n3 0.5 0.5 0.8 0.8\n')
        row=dict(capture_id=name,target_equipment_id=target,
                 objects=[dict(equipment_id='EQ-0001',equipment_type=equipment_type),
                          dict(equipment_id='EQ-0009',equipment_type='CV')])
        (self.captures/(name+'.json')).write_text(json.dumps(row))

    def test_uses_target_even_when_neighbour_box_is_larger(self):
        for split in ('train','val','test'):
            self.photo(split)
        counts=convert(self.dataset,self.out,captures=self.captures)
        for split in ('train','val','test'):
            self.assertEqual(counts[split],{'HPU':1})
            self.assertEqual((self.out/split/'HPU'/('photo-'+split+'.png')).read_bytes(),b'unchanged whole-photograph bytes')

    def test_rejects_missing_or_unknown_target_before_creating_output(self):
        for target,kind in (('missing','HPU'),('EQ-0001','unknown')):
            with self.subTest(target=target,kind=kind):
                self.photo(target=target,equipment_type=kind)
                with self.assertRaises(ValueError):
                    convert(self.dataset,self.out,captures=self.captures)
                self.assertFalse(self.out.exists())

    def test_legacy_largest_box_conversion_remains_available(self):
        self.photo()
        counts=convert(self.dataset,self.out)
        self.assertEqual(counts['train'],{'CV':1})

    def test_cli_accepts_target_metadata(self):
        self.photo()
        result=subprocess.run([sys.executable,'-B','-m','shiftlink.vision.unity_cls',
                               '--dataset',str(self.dataset),'--out',str(self.out),'--captures',str(self.captures)],
                              capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue((self.out/'train/HPU/photo-train.png').is_file())
