"""Card JSON loader, tool binding, and the Ollama query CLI."""

import io
import json
from pathlib import Path

import pytest

from shiftlink.agent.tools import (
    bind_tool_provider,
    get_checklist,
    list_handover,
    lookup_equipment,
    propose_handover,
    search_cards,
    search_safety_cards,
)
from shiftlink.rag.__main__ import main
from shiftlink.rag.loader import load_card_provider


@pytest.fixture(autouse=True)
def _clear_provider():
    bind_tool_provider(None)
    yield
    bind_tool_provider(None)


def card(**overrides):
    data = {
        "card_id": "K-0001",
        "version": "1.0",
        "grade": "L1",
        "tacit_type": "T1",
        "equipment": "HPU",
        "component": "pump",
        "scenario": "S1",
        "title": "압력",
        "symptom": "압력 저하",
        "know_how": "축압기 압력을 확인한다",
        "rationale": "압력 저하 시 확인",
        "confidence": 0.9,
        "provenance": {
            "seed_ids": ["SD-0001"],
            "persona_id": "V-01",
            "event_ids": ["EV-0001"],
            "generator": "test",
            "generated_at": "2026-09-29T00:00:00Z",
        },
        "split": "kb",
        "status": "accepted",
    }
    data.update(overrides)
    return data


def write_json(path: Path, payload) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_loader_keeps_accepted_kb_cards_and_sidecar_rows(tmp_path: Path):
    safety = card(card_id="K-0002", safety_flag=True, safety_basis="방압 후 작업")
    draft = card(card_id="K-0003", status="draft", grade="L0")
    path = write_json(tmp_path / "cards.json", {
        "knowledge_cards": [card(), safety, draft],
        "equipment": [{
            "equipment_id": "EQ-0001",
            "code": "HPU-01",
            "equipment_type_id": "ET-HPU",
        }],
        "equipment_types": [{"equipment_type_id": "ET-HPU", "type_code": "HPU"}],
        "handover": [{"equipment_id": "EQ-0001", "shift": "A", "text": "인계"}],
        "checklist": [{"equipment_id": "EQ-0001", "text": "점검"}],
    })

    loaded = load_card_provider(path)

    assert loaded.seen == 3
    assert loaded.loaded == 2
    assert {item.card_id for item in loaded.provider.cards} == {"K-0001", "K-0002"}
    bind_tool_provider(loaded.provider)
    assert lookup_equipment(equipment_ids=["HPU-01"])[0]["equipment_id"] == "EQ-0001"
    assert {row["card_id"] for row in search_cards(query="압력", equipment_ids=["HPU-01"])} == {
        "K-0001", "K-0002",
    }
    assert [row["card_id"] for row in search_safety_cards(equipment_ids=["HPU-01"])] == ["K-0002"]
    assert list_handover(equipment_ids=["HPU-01"], shift="A")[0]["text"] == "인계"
    assert get_checklist(equipment_ids=["HPU-01"])[0]["text"] == "점검"
    assert propose_handover(extraction_result={"memo": "기록"}) == []


def test_include_draft_loads_draft_kb_cards(tmp_path: Path):
    path = write_json(tmp_path / "cards.json", [card(status="draft", grade="L0")])

    assert load_card_provider(path).loaded == 0
    assert load_card_provider(path, include_draft=True).loaded == 1


def test_loader_reads_a_directory_of_card_files(tmp_path: Path):
    write_json(tmp_path / "b.json", [card(card_id="K-0002", equipment="GR", title="그리퍼")])
    write_json(tmp_path / "a.json", card(card_id="K-0001"))

    loaded = load_card_provider(tmp_path)

    assert loaded.seen == 2
    assert {item.card_id for item in loaded.provider.cards} == {"K-0001", "K-0002"}


def test_loader_rejects_dev_cards_and_broken_json(tmp_path: Path):
    dev = write_json(tmp_path / "dev.json", [card(split="dev")])
    with pytest.raises(ValueError, match="dev/sealed"):
        load_card_provider(dev)

    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON 파싱 실패"):
        load_card_provider(broken)


def test_cli_dry_run_puts_loaded_card_in_the_prompt(tmp_path: Path, capsys):
    path = write_json(tmp_path / "cards.json", [card()])

    status = main([
        "--cards", str(path),
        "--equipment", "HPU",
        "--question", "압력이 떨어졌다",
        "--dry-run",
    ])

    assert status == 0
    text = capsys.readouterr().out
    assert "K-0001" in text
    assert "축압기 압력을 확인한다" in text
    assert "압력이 떨어졌다" in text


def test_cli_answers_from_cards_through_ollama_adapter(tmp_path: Path, monkeypatch, capsys):
    path = write_json(tmp_path / "cards.json", [card()])

    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=None):
        body = {
            "message": {
                "content": json.dumps({
                    "answer": "축압기 압력을 확인한다.",
                    "cited_card_ids": ["K-0001"],
                })
            },
            "load_duration": 0,
            "eval_count": 1,
        }
        return FakeResponse(json.dumps(body).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    status = main([
        "--cards", str(path),
        "--equipment", "HPU",
        "--question", "압력이 떨어졌다",
    ])

    assert status == 0
    text = capsys.readouterr().out
    assert "축압기 압력을 확인한다." in text
    assert "K-0001" in text
