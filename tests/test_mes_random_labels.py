"""Private random-simulation labels must commit with observations."""
import json
import unittest
from datetime import datetime, timezone
from shiftlink.mes.contracts import Run, Snapshot
from shiftlink.mes.storage import MesStorage


class RandomLabelsTests(unittest.TestCase):
    def test_private_atomic_and_matching_tick(self):
        storage = MesStorage()
        self.addCleanup(storage.close)
        run = Run.create(31, datetime(2026, 10, 7, tzinfo=timezone.utc))
        storage.create_run(run)
        snapshot = Snapshot(run.run_id, 1, run.started_at, 'LN-0001', 'running', 'normal')
        labels = {'run_id': run.run_id, 'sequence': 1, 'faults': [{'signal_targets': {'current': 25}}]}
        storage.save_tick(snapshot, simulation_labels=labels)
        row = storage.connection.execute('SELECT payload FROM simulation_labels').fetchone()
        self.assertEqual(json.loads(row[0]), labels)
        self.assertNotIn('signal_targets', json.dumps(storage._public_records(run.run_id)))
        with self.assertRaises(ValueError): storage.save_tick(snapshot, simulation_labels=labels)
        self.assertEqual(storage.connection.execute('SELECT COUNT(*) FROM simulation_labels').fetchone()[0], 1)
        wrong = dict(labels, sequence=2)
        with self.assertRaises(ValueError): storage.save_tick(snapshot, simulation_labels=wrong)

if __name__ == '__main__': unittest.main()
