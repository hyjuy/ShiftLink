"""Live harness instrumentation preserves request and response bytes."""
from io import BytesIO
import json
import urllib.request

from hpu_retrieval_live import profile_requests


def test_profile_does_not_change_model_io(monkeypatch):
    raw=b'{"response":"answer","total_duration":900,"eval_count":5}'
    seen=[]
    def original(request, **kwargs):
        seen.append((request, kwargs))
        return BytesIO(raw)
    monkeypatch.setattr(urllib.request,'urlopen',original)
    events=profile_requests(monkeypatch)
    body=b'{"model":"same-model","prompt":"unchanged","options":{"num_predict":400}}'
    request=urllib.request.Request('http://model/api/generate',data=body)
    assert urllib.request.urlopen(request,timeout=900).read()==raw
    assert seen==[(request,{'timeout':900})] and request.data==body
    assert events[0]['total_duration']==900 and events[0]['eval_count']==5
    assert events[0]['wall_ms']>=0 and 'prompt' not in events[0]
