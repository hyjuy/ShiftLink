"""Durable, idempotent PDA handovers in the local SQLite outbox."""
import tempfile
import unittest
from pathlib import Path

from shiftlink.mes.storage import MesStorage


class HandoverTests(unittest.TestCase):
    def test_outbox_survives_restart_and_retransmission(self):
        payload = {'handover_id': 'HO-0101', 'memo_text': 'GR-01 재점검', 'open_items': []}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'mes.sqlite3'
            first = MesStorage(path)
            try:
                saved = first.save_handover(payload)
                self.assertFalse(saved['duplicate'])
            finally:
                first.close()
            second = MesStorage(path)
            try:
                self.assertEqual(second.get_handover('HO-0101')['payload'], payload)
                again = second.save_handover(payload)
                self.assertTrue(again['duplicate'])
                self.assertEqual(again['created_at'], saved['created_at'])
                self.assertEqual(second.connection.execute('SELECT COUNT(*) FROM handover_outbox').fetchone()[0], 1)
                with self.assertRaisesRegex(ValueError, 'different content'):
                    second.save_handover({**payload, 'memo_text': 'changed'})
                self.assertEqual(second.get_handover('HO-0101')['payload'], payload)
            finally:
                second.close()

    def test_invalid_handover_is_not_stored(self):
        store = MesStorage()
        try:
            for payload in ([], {}, {'handover_id': '', 'memo_text': 'x'},
                            {'handover_id': 'HO-1', 'memo_text': ''},
                            {'handover_id': 1, 'memo_text': 'x'}):
                with self.subTest(payload=payload), self.assertRaises(ValueError):
                    store.save_handover(payload)
            self.assertIsNone(store.get_handover('missing'))
        finally:
            store.close()
