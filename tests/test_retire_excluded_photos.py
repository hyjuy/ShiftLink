import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from scripts.retire_excluded_photos import retire


class RetirePhotosTests(unittest.TestCase):
    def fixture(self, root):
        folder = root / 'captures'
        folder.mkdir()
        (folder / 'bad.png').write_bytes(b'bad')
        (folder / 'bad.json').write_text(json.dumps({'capture_id': 'bad'}))
        (folder / 'keep.png').write_bytes(b'keep')
        excluded = root / 'excluded.jsonl'
        excluded.write_text(json.dumps({'capture_id': 'bad', 'sha256': hashlib.sha256(b'bad').hexdigest()}) + '\n')
        return excluded

    def test_deletes_only_verified_excluded_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = retire(self.fixture(root), [root])
            self.assertEqual(result['deleted_files'], 2)
            self.assertFalse((root / 'captures/bad.png').exists())
            self.assertEqual((root / 'captures/keep.png').read_bytes(), b'keep')

    def test_hash_mismatch_aborts_before_any_deletion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            excluded = self.fixture(root)
            copy = root / 'cnn/train/CAU'
            copy.mkdir(parents=True)
            (copy / 'bad.png').write_bytes(b'changed')
            with self.assertRaises(AssertionError):
                retire(excluded, [root])
            self.assertTrue((root / 'captures/bad.png').exists())
            self.assertTrue((root / 'captures/bad.json').exists())

    def test_malformed_inventory_aborts_before_deletion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            excluded = self.fixture(root)
            (root / 'cnn').mkdir()
            (root / 'cnn/manifest.jsonl').write_text('invalid json')
            with self.assertRaises(json.JSONDecodeError):
                retire(excluded, [root])
            self.assertTrue((root / 'captures/bad.png').exists())
