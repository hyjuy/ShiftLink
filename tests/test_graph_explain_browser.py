"""Actual Chrome PDA -> MES HTTP -> graph -> persisted query; deterministic answer fixture."""
from copy import deepcopy
import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from shiftlink.agent.response import AgentResponse
from test_graph_explain import CARDS
from test_work_report_reuse_harness import service
from test_publication_browser import publication_web


@pytest.mark.parametrize("depth", ["1", "2"])
def test_real_pda_graph_explain(service, publication_web, monkeypatch, tmp_path, depth):
    monkeypatch.setenv("SHIFTLINK_KG_DEPTH", depth)
    api = pytest.importorskip("playwright.sync_api")
    sync_playwright, expect = api.sync_playwright, api.expect
    artifact = Path("docs/demo/kg/.explain-qa");artifact.mkdir(exist_ok=True)
    entered, release = Event(), Event();release.set()
    state = {"withheld":False}
    def answer(payload):
        entered.set();assert release.wait(10)
        return SimpleNamespace(output=AgentResponse(mode="query", answer="원문 카드의 점검 항목을 확인합니다.",
            cited_card_ids=[] if state["withheld"] else ["K-1004", "K-1105"], no_knowledge=state["withheld"]))
    service.query_pipeline = SimpleNamespace(cards=deepcopy(CARDS),run=answer)
    monkeypatch.setenv("SHIFTLINK_KG_MODE", "off")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome",headless=True)
        try:
            page = browser.new_page(viewport={"width":1280,"height":900})
            errors=[];page.on("pageerror",lambda error:errors.append(str(error)))
            page.goto(publication_web + "/pda.html")
            page.wait_for_function("S.equipment.length > 0 && S.cards.length > 0")
            def select():
                page.evaluate("setContext(S.equipment.find(e=>e.equipment_id==='EQ-0001'),'manual_selection'); show('chat')")
            select();page.evaluate("sendChat('펌프 소음과 거품')")
            off=page.evaluate("S.chat.at(-1).response")
            assert "graph_context" not in off
            sensors = page.get_by_role("region",name="MES 센서값",exact=True)
            expect(sensors).to_be_visible()
            sensor_text = sensors.inner_text()
            expect(page.locator(".graph-context")).to_have_count(0)
            monkeypatch.setenv("SHIFTLINK_KG_MODE", "explain")
            select();page.evaluate("sendChat('펌프 소음과 거품')")
            response=page.evaluate("S.chat.at(-1).response")
            assert response["answer"]==off["answer"] and response["evidence"]==off["evidence"]
            assert response["graph_context"]["status"]=="ok"
            assert service.storage.get_query(response["query_id"])["payload"]["graph_context"]==response["graph_context"]
            detail=page.locator(".graph-context");expect(detail).to_be_visible()
            summary=detail.locator(":scope > summary");summary.focus();page.keyboard.press("Enter")
            assert detail.evaluate("e=>e.open")
            expect(detail).to_contain_text("검수 전 증상 후보")
            expect(detail).to_contain_text("판본 미확인 · 보류")
            assert response["cited_card_ids"] == off["cited_card_ids"]
            if depth == "2":
                references = detail.locator(".graph-related").first
                expect(references).to_be_visible()
                assert not references.evaluate("e=>e.open")
                references.locator(":scope > summary").focus();page.keyboard.press("Enter")
                assert references.evaluate("e=>e.open")
                expect(references).to_contain_text("답변 근거에 추가하지 않음")
                expect(references).to_contain_text("K-1008")
                expect(references).to_contain_text("참고 카드 위치")
            else:
                expect(detail.locator(".graph-related")).to_have_count(0)
            for item in response["graph_context"]["cards"]:
                expect(detail).to_contain_text(item["version"])
                for citation in item["citations"]:
                    for locator in citation["locators"]:expect(detail).to_contain_text(locator)
            before=page.evaluate("JSON.stringify(S.chat.at(-1).response.evidence)")
            page.evaluate("loadMesObservations()")
            assert page.evaluate("JSON.stringify(S.chat.at(-1).response.evidence)")==before
            expect(sensors).to_be_visible()
            assert sensors.inner_text() == sensor_text
            for width in (1280,390):
                page.set_viewport_size({"width":width,"height":900})
                assert detail.evaluate("e=>e.scrollWidth<=e.clientWidth+1")
                page.screenshot(path=str(artifact/f"pda-explain-depth{depth}-{width}.png"),full_page=True)
                if depth == "2":
                    ref_summary = references.locator(":scope > summary")
                    ref_summary.scroll_into_view_if_needed()
                    expect(ref_summary).to_be_in_viewport()
                    page.screenshot(path=str(artifact/f"two-hop-references-{width}.png"),full_page=True)
                    ref_last = references.locator("p").last
                    ref_last.scroll_into_view_if_needed()
                    expect(ref_last).to_be_in_viewport()
                    assert ref_last.evaluate("e=>{const r=e.getBoundingClientRect();return e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}")
                detail.scroll_into_view_if_needed()
                # A long disclosure lives in the existing chat scroller; verify its last line is reachable.
                last = detail.locator("p").last
                last.scroll_into_view_if_needed()
                expect(last).to_be_in_viewport()
                assert last.evaluate("e=>{const r=e.getBoundingClientRect();return e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}")
                page.screenshot(path=str(artifact/f"pda-graph-depth{depth}-{width}.png"),full_page=True)
            monkeypatch.setenv("SHIFTLINK_KG_PATH",str(tmp_path/"missing.json"))
            select();page.evaluate("sendChat('펌프 소음과 거품')")
            failed=page.evaluate("S.chat.at(-1).response")
            assert failed["answer"]==off["answer"] and failed["graph_context"]["status"]=="unavailable"
            page.locator(".graph-context summary").click()
            expect(page.locator(".graph-context")).to_contain_text("기존 답변은 그대로")
            state["withheld"]=True
            select();page.evaluate("sendChat('근거 부족 질문')")
            expect(page.locator(".graph-context")).to_have_count(0)
            # A response arriving after equipment selection changed cannot paint stale graph details.
            state["withheld"]=False;entered.clear();release.clear()
            select();page.evaluate("void sendChat('지연된 질문')")
            assert entered.wait(5)
            page.evaluate("setContext(S.equipment.find(e=>e.equipment_id==='EQ-0004'),'manual_selection')")
            release.set()
            page.wait_for_function("S.eq.equipment_id==='EQ-0004' && S.chat.length===0")
            page.wait_for_timeout(300)
            expect(page.locator(".graph-context")).to_have_count(0)
            assert page.evaluate("S.queryResponse === null")
            assert errors==[]
            (artifact/f"browser-response-depth{depth}.json").write_text(json.dumps(response,ensure_ascii=False,indent=2),encoding="utf-8")
        finally:
            release.set();browser.close()
