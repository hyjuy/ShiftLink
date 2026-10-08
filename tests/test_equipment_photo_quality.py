import unittest
from scripts.curate_equipment_cnn import quality_reasons


class EquipmentPhotoQualityTests(unittest.TestCase):
    def photo(self,box=None,**changes):
        row=dict(image_width=1280,image_height=720,target_equipment_id='target',shot_kind='whole',
                 objects=[dict(equipment_id='target',equipment_type='CAU',bbox_xyxy=box or [200,100,1000,650])])
        row.update(changes)
        return row

    def test_keeps_identifiable_target_in_dim_but_readable_photo(self):
        self.assertEqual(quality_reasons(self.photo(),35,20),[])

    def test_excludes_small_dark_and_flat_photos(self):
        self.assertIn('small_target',quality_reasons(self.photo([500,250,650,400]),80,30))
        self.assertIn('too_dark',quality_reasons(self.photo(),10,20))
        self.assertIn('low_contrast',quality_reasons(self.photo(),70,3))

    def test_excludes_dominant_unrelated_equipment(self):
        row=self.photo([400,200,900,600])
        row['objects'].append(dict(equipment_id='other',equipment_type='CV',bbox_xyxy=[0,0,1000,700]))
        self.assertIn('dominant_other_class',quality_reasons(row,80,30))

    def test_requires_visible_characteristic_feature_for_detail(self):
        row=self.photo(shot_kind='detail',feature_name='ControlDisplay',feature_visible=False)
        self.assertIn('hidden_or_missing_feature',quality_reasons(row,80,30))
        row['feature_visible']=True
        self.assertEqual(quality_reasons(row,80,30),[])

    def test_same_class_neighbor_is_not_an_unrelated_label(self):
        row=self.photo()
        row['objects'].append(dict(equipment_id='second',equipment_type='CAU',bbox_xyxy=[0,0,1280,720]))
        self.assertEqual(quality_reasons(row,80,30),[])
