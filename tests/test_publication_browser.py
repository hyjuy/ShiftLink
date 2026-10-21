"""Real browser + real MES HTTP; embedding output is an explicit deterministic fixture."""
import hashlib
import json
import os
from pathlib import Path
from http.server import ThreadingHTTPServer
from threading import Thread, Event

import pytest

from test_work_report_reuse_harness import service
from test_work_report_capture import captured
from test_publication_worker import vectors
from shiftlink.mes.accounts import Accounts
from shiftlink.mes.server import _Handler


@pytest.fixture
def publication_web(service,tmp_path):
    accounts = Accounts(tmp_path/'accounts.json')
    salt = b'publication-browser-tests'
    entries=[]
    for role,identifier in [('admin','reviewer'),('operator','WORKER-01')]:
        entries.append({'id':identifier,'name':'검증 '+identifier,'role':role,'salt':salt.hex(),
            'hash':hashlib.scrypt(b'local-publication-test',salt=salt,n=16384,r=8,p=1).hex()})
    accounts.path.write_text(json.dumps(entries),encoding='utf-8')
    server = ThreadingHTTPServer(('127.0.0.1',0),type('PublicationBrowserHandler',(_Handler,),{
        'service':service,'accounts':accounts,'web_root':Path('shiftlink/mes/web'),'log_message':lambda *args:None}))
    worker = Thread(target=server.serve_forever);worker.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown();worker.join();server.server_close()


def test_question_report_review_quality_publish_browser_flow(service, publication_web):
    api = pytest.importorskip('playwright.sync_api')
    sync_playwright,expect = api.sync_playwright,api.expect
    artifact = Path('artifacts/knowledge-publication-20261021');artifact.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as playwright:
        channel = os.environ.get('SHIFTLINK_BROWSER_CHANNEL','chrome')
        browser=playwright.chromium.launch(headless=True,**({'channel':channel} if channel else {}))
        try:
            page=browser.new_page(viewport={'width':1280,'height':900})
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            # HTTP APIs used by the PDA preserve the query -> log source chain.
            question=page.request.post(publication_web+'/api/query',data={
                'question':'압력이 낮고 필터 오염이 의심됩니다','equipment_id':service.active_config.equipment[0].equipment_id}).json()
            assert question['knowledge_status']=='no_applicable_card'
            note=captured(service)
            note['work_report']['records'][0]['query_id']=question['query_id']
            saved=page.request.post(publication_web+'/api/work-reports',data=note).json()
            draft_id=saved['candidates'][0]['draft_id']
            page.goto(publication_web+'/knowledge-candidates.html')
            page.locator('#review-admin-id').fill('reviewer')
            page.locator('#review-admin-password').fill('local-publication-test')
            page.locator('#review-login-form button').click()
            expect(page.locator('#candidate-detail h2')).to_contain_text('HPU')
            assert page.get_by_role('button',name='검수 통과',exact=True).count()==0
            page.locator('#review-reason').fill('원문·조치 결과 심사 완료')
            page.get_by_role('button',name='검토 승인',exact=True).click()
            expect(page.get_by_role('button',name='검수 통과',exact=True)).to_be_visible()
            page.locator('#review-reason').fill('적용 범위·안전·조치 결과 검수 완료')
            page.get_by_role('button',name='검수 통과',exact=True).click()
            expect(page.locator('#publication-state')).to_have_text('임베딩 대기')
            expect(page.locator('#publication-search')).to_have_text('아직 검색에 사용하지 않음')
            # Exercise a real worker commit, then the actual refresh/render path.
            assert service.publications.process_one(embedder=vectors)
            page.locator('#candidate-status').select_option('quality_passed')
            page.locator('#review-refresh').click()
            expect(page.locator('#publication-state')).to_have_text('검색 반영 완료')
            expect(page.locator('#publication-search')).to_have_text('후속 질문의 검색 후보로 사용')
            page.get_by_text('구조화된 카드 보기',exact=True).click()
            expect(page.locator('#publication-json')).to_contain_text('accepted')
            for width in (1280,390):
                page.set_viewport_size({'width':width,'height':900})
                page.evaluate('scrollTo(0,0)')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.screenshot(path=str(artifact/f'review-{width}.png'),full_page=True)
            response=page.request.post(publication_web+'/api/query',data={
                'question':'필터 오염 확인 필터 교체 압력','equipment_id':note['equipment_id']}).json()
            assert draft_id in response['cited_card_ids']
            page.locator('#review-reason').fill('반대 근거 발견으로 재검토')
            page.get_by_role('button',name='보완 요청',exact=True).click()
            expect(page.locator('#publication-state')).to_have_text('재검토로 검색 제외')
            assert page.request.post(publication_web+'/api/query',data={
                'question':'필터 오염 확인 필터 교체 압력','equipment_id':note['equipment_id']}).json()['no_knowledge']
            assert errors==[]
        finally:
            browser.close()
