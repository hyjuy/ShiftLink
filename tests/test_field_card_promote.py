"""시연용 현장 카드 승격·원복 도구(scripts/field_card_promote.py)."""
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from shiftlink.mes.server import MesService
from shiftlink.mes.storage import MesStorage
from shiftlink.rag.loader import load_card_provider

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("field_card_promote", ROOT / "scripts/field_card_promote.py")
promote = importlib.util.module_from_spec(spec)
spec.loader.exec_module(promote)
KB = ROOT / "docs/data/knowledge_cards/kb/kb_cards.json"
CATALOG = ROOT / "docs/data/reference/00_plant_and_relations.json"


class FieldCardPromoteTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        tmp = Path(self.directory.name)
        self.kb = tmp / "kb_cards.json"
        shutil.copy2(KB, self.kb)
        # 실제 흐름으로 초안 1장: 과열 → 조치 기록 → MES 복구 → 저장
        service = MesService(CATALOG, MesStorage(tmp / "mes.sqlite3"))
        service.control({"command": "start"}); service.engine.tick(30)
        service.control({"command": "scenario", "scenario_id": "hydraulic_overheat"}); service.engine.tick(5)
        sid = service.resolution_start({"equipment_id": "EQ-0001"})["session_id"]
        service.resolution_step(sid, {"action": "팬 차단기 트립 원인 확인 후 재투입", "lockout": "예"})
        for action in ("verify",):
            service.control({"command": "recovery_action", "action_id": action})
        service.control({"command": "recover"}); service.engine.tick(5)
        service.resolution_step(sid, {"action": "팬 회전 방향과 소리 확인"})
        service.record_handover({"handover_id": "HO-P1", "memo_text": "m", "equipment_id": "EQ-0001", "resolution": {
            "session_id": sid, "symptom": "쿨러 팬이 멈춰 있고 차단기가 트립돼 있음", "cause": "팬 차단기 트립",
            "component_id": "cooling", "result": "resolved"}})
        self.row = service.card_drafts()["drafts"][0]
        service.storage.close()

    def tearDown(self):
        self.directory.cleanup()

    def test_draft_lists_similar_existing_cards(self):
        self.assertIn("K-1002", [c["card_id"] for c in self.row["similar_kb_cards"]])
        self.assertIn("겹칠 수 있는 기존 카드: K-1002", promote.describe(self.row))

    def test_promote_then_restore_round_trip(self):
        original = self.kb.read_bytes()
        card = promote.promoted_card(self.row)
        self.assertEqual((card["status"], card["grade"], card["split"]), ("accepted", "L1", "kb"))
        backup = promote.promote_local(self.kb, card)
        self.assertEqual(backup.read_bytes(), original)
        provider = load_card_provider(self.kb).provider
        self.assertIn(card["card_id"], [c.card_id for c in provider.cards])  # 검색 대상이 됐다
        with self.assertRaises(ValueError):  # 같은 카드 두 번은 안 된다
            promote.promote_local(self.kb, card)
        self.assertTrue(promote.restore_local(self.kb))
        self.assertEqual(self.kb.read_bytes(), original)
        self.assertFalse(backup.exists())
        self.assertFalse(promote.restore_local(self.kb))

    def test_only_pending_review_drafts(self):
        with self.assertRaises(ValueError):
            promote.promoted_card({**self.row, "status": "invalid"})


if __name__ == "__main__":
    unittest.main()
