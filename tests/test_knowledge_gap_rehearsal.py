"""지식 공백 채우기 시연 리허설 — docs/testing/knowledge-gap-demo.md 의 장면을 순서대로 서버 함수로 돌려
단계마다 대시보드 지식 공백 숫자(/api/analytics 의 knowledge)가 상황지대로 바뀌는지 본다.

판정 모델은 쓰지 않는다: 승인 전 질문은 검색 후보 카드가 없어 판정 없이 '해당 지식 없음'이 되고,
승인 뒤에는 판정을 '답 가능'으로 고정한 파이프라인(시험용)을 쓴다. 실제 판정 모델의 판단은 Jetson에서 확인한다.
"""
import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from shiftlink.agent.pipeline import FixedPipeline
from shiftlink.mes import server as mes_server
from shiftlink.mes.server import MesService
from shiftlink.mes.storage import MesStorage
from shiftlink.rag.loader import load_card_provider

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs/data/reference/00_plant_and_relations.json"
KB = ROOT / "docs/data/knowledge_cards/kb/kb_cards.json"
spec = importlib.util.spec_from_file_location("field_card_promote", ROOT / "scripts/field_card_promote.py")
promote = importlib.util.module_from_spec(spec)
spec.loader.exec_module(promote)

QUESTION = "작동유 온도가 너무 높아요"


class KnowledgeGapRehearsal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.kb = Path(self.tmp.name) / "kb_cards.json"
        shutil.copy2(KB, self.kb)   # 승격은 복사본에만 — 저장소 카드 묶음은 건드리지 않는다
        patcher = mock.patch.object(mes_server, "_KB_CARDS", self.kb)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.service = MesService(CATALOG, MesStorage(Path(self.tmp.name) / "mes.sqlite3"))
        self.service.control({"command": "start"})
        self.service.engine.tick(30)

    def tearDown(self):
        self.service.storage.close()
        self.tmp.cleanup()

    def gap(self):
        k = self.service.analytics()["knowledge"]
        return (k["no_knowledge"], k["drafts"], k["pending"], k["approved"], k["answered"])

    def overheat(self):
        self.service.control({"command": "reset"})
        self.service.control({"command": "start"})
        self.service.engine.tick(30)
        self.service.control({"command": "scenario", "scenario_id": "hydraulic_overheat"})
        self.service.engine.tick(5)

    def ask(self, question=QUESTION):
        return self.service.query({"question": question, "equipment_id": "EQ-0001"})

    def record(self, handover_id, answer, symptom, actions, cause, *, mes=True, result=None):
        """PDA 조치 기록: 조치 시작 → (직접 조치) → MES 단계 3 + 재가동 → 마무리 → 인계와 함께 저장."""
        sid = self.service.resolution_start({"equipment_id": "EQ-0001", "question": QUESTION, "evidence": answer["evidence"],
                                             "card_ids": answer.get("cited_card_ids") or []})["session_id"]
        for action, lockout in actions:
            self.service.resolution_step(sid, {"action": action, "lockout": lockout})
        if mes:
            for action_id in ("verify",):
                self.service.control({"command": "recovery_action", "action_id": action_id})
            self.service.control({"command": "recover"})
            self.service.engine.tick(5)
            self.service.resolution_step(sid, {"action": "유온·공급 정상 확인"})
        verdict = self.service.resolution_finish(sid)
        return self.service.record_handover({"handover_id": handover_id, "memo_text": "조치 기록", "equipment_id": "EQ-0001",
                                             "resolution": {"session_id": sid, "symptom": symptom, "cause": cause,
                                                            "component_id": "cooling",
                                                            "result": result or verdict["suggested_result"]}})

    def test_gap_is_found_filled_and_closed(self):
        self.assertEqual(self.gap(), (0, 0, 0, 0, 0))   # 시연 시작: 테스트 데이터를 비운 DB

        # 장면 1 공백 발견 — 카드에 없는 상황
        self.overheat()
        a = self.ask()
        self.assertTrue(a["no_knowledge"])
        self.assertEqual(self.gap(), (1, 0, 0, 0, 0))

        # 장면 2 기록 → 초안: 팬 차단기 트립
        out = self.record("HO-G1", a, "쿨러 팬이 멈춰 있고 팬 전원 차단기가 트립돼 있음", [("팬 차단기 트립 원인 확인 후 재투입", "예")], "팬 차단기 트립")
        self.assertEqual((out["draft"]["reason"], out["draft"]["mes_verdict"]), ("pending_review", "recovered"))
        self.assertEqual(self.gap(), (1, 1, 1, 0, 0))

        # 장면 3 같은 원인, 다른 사람 — 초안이 늘지 않고 근거가 붙는다
        self.overheat()
        a = self.ask("유압유 온도 경보가 계속 떠요")
        self.assertTrue(a["no_knowledge"])
        out = self.record("HO-G2", a, "쿨러 쪽이 조용하고 팬이 안 돎", [("팬 차단기 올림", "예")], "팬 차단기 트립")
        self.assertEqual(out["draft"]["reason"], "supporting")
        self.assertEqual(self.gap(), (2, 1, 1, 0, 0))

        # 장면 4 다른 원인 — 새 초안
        self.overheat()
        a = self.ask("유온이 78도까지 올라갔어요")
        out = self.record("HO-G3", a, "팬은 도는데 쿨러 핀 사이에 먼지와 기름때가 꽉 참", [("쿨러 핀 에어 블로우로 먼지 제거", None)], "쿨러 핀 막힘")
        self.assertEqual(out["draft"]["reason"], "pending_review")
        self.assertEqual(self.gap(), (3, 2, 2, 0, 0))

        # 장면 5 승인 — 관리자가 K-7000을 카드 묶음에 넣는다(시연용 승격 도구)
        row = next(r for r in self.service.card_drafts()["drafts"] if "팬 차단기 트립" in r["card"]["title"])
        self.assertTrue(row["review_flags"]["completeness"]["ready"])   # 장면 2·3의 MES 확인 해결 2건 → --force 없이 승격
        promote.promote_local(self.kb, promote.promoted_card(row))
        self.assertEqual(self.gap(), (3, 2, 1, 1, 0))
        self.assertEqual(self.service.analytics()["knowledge"]["approved_ids"], [row["card"]["card_id"]])

        # 장면 6 다음 교대, 같은 질문 → 현장 카드로 답한다(공백이 닫힘). 판정은 '답 가능'으로 고정(시험용)
        self.service.query_pipeline = FixedPipeline(model=lambda **_: {}, tools=load_card_provider(self.kb).provider,
                                                    answer_mode="extract", judge=lambda q, c: 3)
        self.overheat()
        a = self.ask()
        self.assertFalse(a["no_knowledge"])
        self.assertIn(row["card"]["card_id"], a["cited_card_ids"])
        self.assertEqual(self.gap(), (3, 2, 1, 1, 1))

        # 장면 7 카드를 보고 조치 — 새 초안을 만들지 않는다(카드 효과 기록)
        out = self.record("HO-G4", a, "쿨러 팬이 멈춰 있고 차단기가 떨어져 있음", [("팬 차단기 트립 원인 확인 후 재투입", "예")], "팬 차단기 트립")
        self.assertEqual(out["draft"]["reason"], "card_used")
        self.assertEqual(self.gap(), (3, 2, 1, 1, 1))


if __name__ == "__main__":
    unittest.main()
