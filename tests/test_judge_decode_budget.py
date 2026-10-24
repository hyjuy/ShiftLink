"""Stop after the existing score token; keep legacy fallback and probabilities."""
from io import BytesIO
import json
import math
import urllib.request

import pytest

from shiftlink.rag2 import evidence_score as E

CHUNK={'metadata':{'source':'K-source','section':'same title'},'text':'same original evidence'}


def distribution():
    return [{'token':'{"score": ','top_logprobs':[]},
            {'token':'2','top_logprobs':[{'token':str(i),'logprob':math.log(p)}
                                        for i,p in enumerate((.1,.2,.3,.4))]}]


def respond(monkeypatch, responses):
    seen=[]
    def open_request(request, **kwargs):
        seen.append((request.full_url,json.loads(request.data),kwargs))
        return BytesIO(json.dumps(responses[len(seen)-1]).encode())
    monkeypatch.setattr(urllib.request,'urlopen',open_request)
    monkeypatch.setattr(E.time,'sleep',lambda *a:None)
    return seen


def test_known_judge_only_decodes_through_its_score(monkeypatch):
    seen=respond(monkeypatch,[{'logprobs':distribution()}])
    result=E.judge_dist('same question',CHUNK,'http://judge',ctx=2048)
    assert result==pytest.approx([.1,.2,.3,.4])
    url,body,kwargs=seen[0]
    assert url=='http://judge/api/chat' and kwargs=={'timeout':300}
    assert body['options']=={'temperature':0,'num_ctx':2048,'num_predict':6}
    assert body['messages'][1]['content']=='질문: same question\n\n카드 제목: same title\n증상: -\n내용: same original evidence'
    assert body['messages'][0]['content']==E.JUDGE_PROMPT and body['logprobs']
    assert body['format']['properties']['score']['enum']==[0,1,2,3]


def test_missing_score_uses_original_budget_without_accepting_a_guess(monkeypatch):
    seen=respond(monkeypatch,[{'logprobs':[]},{'logprobs':distribution()}])
    assert E.judge_dist('question',CHUNK,'http://judge')==pytest.approx([.1,.2,.3,.4])
    assert [b['options']['num_predict'] for _,b,_ in seen]==[6,20]
    first,second=[body for _,body,_ in seen]
    first['options']['num_predict']=20
    assert first==second


def test_other_model_keeps_original_budget(monkeypatch):
    seen=respond(monkeypatch,[{'logprobs':distribution()}])
    assert E.judge_dist('question',CHUNK,'http://judge',model='other-model')
    assert seen[0][1]['options']['num_predict']==20


def test_no_score_still_fails_closed(monkeypatch):
    seen=respond(monkeypatch,[{'logprobs':[]}]*3)
    assert E.judge_dist('question',CHUNK,'http://judge') is None
    assert [b['options']['num_predict'] for _,b,_ in seen]==[6,20]
