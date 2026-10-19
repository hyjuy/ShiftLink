"""Administrator-only review preserves original drafts and never publishes them."""
import hashlib
import json
from pathlib import Path
from threading import Thread
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError

import pytest
from test_work_report_capture import captured
from test_work_report_reuse_harness import service
from shiftlink.mes.accounts import Accounts
from shiftlink.mes.server import _Handler
from shiftlink.mes.storage import MesStorage


@pytest.fixture
def review_api(service,tmp_path):
    salt=b'local-review-tests'
    account=Accounts(tmp_path/'accounts.json')
    account.path.write_text(json.dumps([{'id':'reviewer','name':'검토 관리자','role':'admin','salt':salt.hex(),
        'hash':hashlib.scrypt(b'isolated-review-test',salt=salt,n=16384,r=8,p=1).hex()}]),encoding='utf-8')
    server=ThreadingHTTPServer(('127.0.0.1',0),type('ReviewHandler',(_Handler,),{
        'service':service,'accounts':account,'web_root':Path('shiftlink/mes/web'),'log_message':lambda *args:None}))
    thread=Thread(target=server.serve_forever);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    def request(path,payload=None,token=None):
        headers={'Content-Type':'application/json'}
        if token:headers['Authorization']='Bearer '+token
        data=None if payload is None else json.dumps(payload).encode()
        with urlopen(Request(base+path,data,headers),timeout=5) as response:return json.load(response)
    token=request('/api/admin/login',{'id':'reviewer','password':'isolated-review-test'})['token']
    saved=service.record_work_report(captured(service))
    draft_id=saved['candidates'][0]['draft_id']
    try:yield request,token,draft_id,account
    finally:server.shutdown();thread.join();server.server_close()


def test_admin_review_is_durable_audited_and_not_published(service,review_api):
    request,token,draft_id,_=review_api
    original=service.storage.list_card_drafts()[0]['card']
    listing=request('/api/admin/card-drafts',token=token)
    assert listing['drafts'][0]['draft_id']==draft_id
    detail=request('/api/admin/card-drafts/'+draft_id,token=token)['draft']
    assert detail['revision']==0 and detail['sources'][0]['work_report']['records']
    reviewed=request('/api/admin/card-drafts/'+draft_id+'/review',{
        'action':'approve','reason':'원인·조치 결과·정상 운전 확인 검토','expected_revision':0},token)['draft']
    assert reviewed['status']=='review_approved' and reviewed['revision']==1
    assert reviewed['card']==original and reviewed['card']['status']=='draft'
    assert reviewed['reviews'][0]['reviewer_id']=='reviewer'
    assert reviewed['reviews'][0]['reviewer_name']=='검토 관리자'
    assert reviewed['reviews'][0]['created_at']
    path=Path(service.storage.connection.execute('PRAGMA database_list').fetchone()[2])
    reopened=MesStorage(path)
    try:assert reopened.get_card_draft(draft_id)['reviews']==reviewed['reviews']
    finally:reopened.close()


@pytest.mark.parametrize('route',['/api/admin/card-drafts','/api/admin/card-drafts/K-7000'])
def test_candidate_management_requires_admin_session(review_api,route):
    request,_,_,_=review_api
    with pytest.raises(HTTPError) as caught:request(route)
    assert caught.value.code==401


def test_review_rejects_stale_version_and_missing_reason(review_api):
    request,token,draft_id,_=review_api
    route='/api/admin/card-drafts/'+draft_id+'/review'
    for action in ['request_changes','reject']:
        with pytest.raises(HTTPError) as caught:request(route,{'action':action,'reason':'','expected_revision':0},token)
        assert caught.value.code==400
    request(route,{'action':'request_changes','reason':'관찰 구간 보완 필요','expected_revision':0},token)
    with pytest.raises(HTTPError) as caught:request(route,{'action':'approve','reason':'','expected_revision':0},token)
    assert caught.value.code==409
    detail=request('/api/admin/card-drafts/'+draft_id,token=token)['draft']
    assert detail['status']=='changes_requested' and len(detail['reviews'])==1


def test_expired_session_and_forged_reviewer_cannot_review(review_api):
    request,token,draft_id,accounts=review_api
    route='/api/admin/card-drafts/'+draft_id+'/review'
    with pytest.raises(HTTPError) as caught:
        request(route,{'action':'approve','reason':'','expected_revision':0,'reviewer_id':'someone_else'},token)
    assert caught.value.code==400
    accounts.sessions[token]=0
    with pytest.raises(HTTPError) as caught:request(route,{'action':'approve','reason':'','expected_revision':0},token)
    assert caught.value.code==401
