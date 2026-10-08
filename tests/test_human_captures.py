"""Validate the acceptance gate used on rendered Unity camera metadata."""
import json
import math
import tempfile
import unittest
from pathlib import Path

from scripts.check_human_captures import check


class HumanCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def photo(self, index=0, **changes):
        level=(.35,1,1.6,.8,.8)[index % 5]
        sector, slot = divmod(index, 50)
        angle=sector*30+10
        row = dict(camera_pose={'position': [3*math.cos(math.radians(angle)), 1.5, 3*math.sin(math.radians(angle))]}, viewpoint='handheld-first-person',
                   standpoint_clear=True, lighting_profile=('dim', 'normal', 'bright', 'warm', 'cool')[index % 5],
                   sun_intensity=level, interior_light_intensity=2*level, ambient_rgb=[.28*level]*3,
                   dataset_split='train' if slot < 40 else 'val' if slot < 45 else 'test',
                   shot_kind='whole' if (slot+sector)%2==0 else 'detail',
                   direction_sector=sector, azimuth_degrees=angle, target_center=[0,1,0],
                   feature_name='ControlDisplay', feature_visible=True,
                   target_equipment_id='EQ-0001', objects=[{'equipment_id': 'EQ-0001'}])
        row.update(changes)
        (self.root / f'{index}.json').write_text(json.dumps(row))

    def test_accepts_balanced_render_metadata(self):
        for i in range(600):
            self.photo(i)
        self.assertEqual(check(self.root), {'EQ-0001': 600})

    def test_rejects_unusable_camera_and_unlabelled_target(self):
        for changes in ({'camera_pose': {'position': [0, 2.3, 3]}}, {'standpoint_clear': False},
                        {'viewpoint': 'third-person'}, {'lighting_profile': 'unknown'}, {'objects': []}):
            with self.subTest(changes=changes):
                self.photo(**changes)
                with self.assertRaises(AssertionError):
                    check(self.root, 1)

    def test_rejects_missing_lighting_in_test_split(self):
        for i in range(600):
            self.photo(i, **({'lighting_profile': 'normal'} if i % 50 >= 45 else {}))
        with self.assertRaises(AssertionError):
            check(self.root)

    def test_rejects_empty_or_incomplete_collection(self):
        with self.assertRaises(AssertionError):
            check(self.root)
        self.photo()
        with self.assertRaises(AssertionError):
            check(self.root)

    def test_accepts_person_standing_on_real_elevated_platform(self):
        self.photo(camera_pose={'position': [0, 4.7, 3]}, standing_floor_y=3.2,
                   direction_sector=3, azimuth_degrees=90)
        self.assertEqual(check(self.root, 1), {'EQ-0001': 1})

    def test_rejects_invalid_recorded_light_brightness(self):
        for changes in ({'sun_intensity': 0}, {'interior_light_intensity': float('nan')}, {'ambient_rgb': [-1, 0, 0]}):
            with self.subTest(changes=changes):
                self.photo(**changes)
                with self.assertRaises(AssertionError):
                    check(self.root, 1)

    def test_rejects_profiles_with_identical_brightness(self):
        for i in range(600):
            self.photo(i, sun_intensity=1, interior_light_intensity=2)
        with self.assertRaises(AssertionError):
            check(self.root)

    def test_rejects_one_sided_collection_and_missing_detail_views(self):
        for changes in ({'direction_sector': 0, 'azimuth_degrees': 10,
                         'camera_pose': {'position': [2.9544,1.5,.5209]}}, {'shot_kind': 'whole'}):
            with self.subTest(changes=changes):
                for i in range(600):
                    self.photo(i, **changes)
                with self.assertRaises(AssertionError):
                    check(self.root)

    def test_rejects_false_direction_or_hidden_feature(self):
        for changes in ({'direction_sector': 6}, {'shot_kind': 'detail', 'feature_name': ''},
                        {'shot_kind': 'detail', 'feature_visible': False}):
            with self.subTest(changes=changes):
                self.photo(**changes)
                with self.assertRaises(AssertionError):
                    check(self.root, 1)
