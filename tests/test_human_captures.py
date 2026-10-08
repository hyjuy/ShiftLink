"""Validate the acceptance gate used on rendered Unity camera metadata."""
import json
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
        row = dict(camera_pose={'position': [0, 1.5, 3]}, viewpoint='handheld-first-person',
                   standpoint_clear=True, lighting_profile=('dim', 'normal', 'bright', 'warm', 'cool')[index % 5],
                   sun_intensity=level, interior_light_intensity=2*level, ambient_rgb=[.28*level]*3,
                   dataset_split='train' if index < 480 else 'val' if index < 540 else 'test',
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
            self.photo(i, **({'lighting_profile': 'normal'} if i >= 540 else {}))
        with self.assertRaises(AssertionError):
            check(self.root)

    def test_rejects_empty_or_incomplete_collection(self):
        with self.assertRaises(AssertionError):
            check(self.root)
        self.photo()
        with self.assertRaises(AssertionError):
            check(self.root)

    def test_accepts_person_standing_on_real_elevated_platform(self):
        self.photo(camera_pose={'position': [0, 4.7, 3]}, standing_floor_y=3.2)
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
