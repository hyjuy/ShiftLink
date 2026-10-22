"""Real Chrome inventory and existing dashboard with actual local HTTP APIs."""
from pathlib import Path
import pytest
from test_publication_browser import publication_web
from test_work_report_reuse_harness import service
from test_work_report_capture import captured
from test_publication_worker import vectors


def test_inventory_preserves_dashboard_and_publication_states(service,publication_web):
    api=pytest.importorskip('playwright.sync_api');expect=api.expect
    saved=service.record_work_report(captured(service));draft_id=saved['candidates'][0]['draft_id']
    actor={'id':'reviewer','name':'검증 관리자'}
    def decide(action,revision):
        service.review_card_draft(draft_id,{'action':action,'reason':'원문과 적용 범위 확인','expected_revision':revision},actor)
    with api.sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True)
        try:
            page=browser.new_page(viewport={'width':1280,'height':900});errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(publication_web+'/pda.html')
            page.wait_for_function("S.equipment.length>0 && document.querySelector('#knowledgeDashboard').textContent.includes('86')")
            page.evaluate("$('toDashboard').click()")
            expect(page.locator('#anGap .an-flow')).to_be_visible()
            expect(page.locator('#knowledgeOpen')).to_be_visible()
            page.locator('#knowledgeOpen').focus();page.keyboard.press('Enter')
            expect(page.locator('#s-knowledge')).to_be_visible()
            expect(page.locator('.knowledge-row')).to_have_count(86)
            page.locator('#knowledgeSearch').fill('K-1004')
            expect(page.locator('.knowledge-row')).to_have_count(1)
            expect(page.locator('#knowledgeDetail')).to_contain_text('K-1004')
            expect(page.locator('#knowledgeDetail')).to_contain_text('출처')
            page.locator('#knowledgeSearch').fill('')
            page.locator('#knowledgeState').select_option('pending_review')
            expect(page.locator('#knowledgeDetail')).to_contain_text('원본 근무일지')
            decide('approve',0);decide('quality_pass',1)
            page.locator('#knowledgeRefresh').click();page.locator('#knowledgeState').select_option('quality_passed')
            expect(page.locator('#knowledgeDetail')).to_contain_text('임베딩 대기')
            expect(page.locator('#knowledgeDetail')).to_contain_text('검색에 사용하지 않음')
            assert service.publications.process_one(embedder=vectors)
            page.locator('#knowledgeRefresh').click()
            expect(page.locator('#knowledgeDetail')).to_contain_text('검색 반영 완료')
            expect(page.locator('#knowledgeDetail')).to_contain_text('적용 설비·조건은 질의 시 확인')
            decide('request_changes',2)
            page.locator('#knowledgeRefresh').click();page.locator('#knowledgeState').select_option('changes_requested')
            expect(page.locator('#knowledgeDetail')).to_contain_text('재검토로 검색 제외')
            artifacts=Path('docs/demo/kg/.jetson-sync-qa/browser');artifacts.mkdir(parents=True,exist_ok=True)
            for width in (1280,390):
                page.set_viewport_size({'width':width,'height':900})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                assert page.locator('.knowledge-heading h1').bounding_box()['height']<70
                if width<700:
                    row=page.locator('.knowledge-list').bounding_box()
                    detail=page.locator('.knowledge-detail').bounding_box()
                    assert detail['y']>=row['y']+row['height']
                page.screenshot(path=str(artifacts/f'inventory-{width}.png'),full_page=True)
            page.locator('#knowledgeBack').click()
            expect(page.locator('#anGap .an-flow')).to_be_visible()
            expect(page.locator('#knowledgeDashboard')).to_have_count(1)
            page.evaluate("$('toDashboard').click()")
            expect(page.locator('#knowledgeDashboard')).to_have_count(1)
            page.evaluate("setContext(S.equipment.find(e=>e.equipment_id==='EQ-0001'),'manual_selection');show('ctx')")
            expect(page.get_by_role('region',name='MES 센서값',exact=True)).to_be_visible()
            page.screenshot(path=str(artifacts/'sensors-390.png'),full_page=True)
            page.route('**/api/knowledge-cards',lambda route:route.fulfill(status=503,content_type='application/json',body='{}'))
            page.evaluate("$('toDashboard').click()")
            page.locator('#knowledgeOpen').click()
            expect(page.locator('#knowledgeStatus')).to_contain_text('불러오지 못했습니다')
            expect(page.locator('.knowledge-row')).to_have_count(0)
            assert not errors,errors
        finally:browser.close()
