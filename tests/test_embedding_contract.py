"""Real HTTP request contract; deterministic responses are not real model evidence."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.error import HTTPError

import pytest

from shiftlink.rag.embedding import normalise, ollama_embed, prefixes


def test_real_http_embedding_request_and_normalisation():
    seen=[]
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            seen.append((self.path,self.headers['Content-Type'],body))
            output=json.dumps({'embeddings':[[3,4],[0,2]]}).encode()
            self.send_response(200);self.send_header('Content-Length',str(len(output)));self.end_headers();self.wfile.write(output)
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=server.serve_forever);thread.start()
    try:
        raw=ollama_embed(['doc one','doc two'],'embeddinggemma:300m',f'http://127.0.0.1:{server.server_port}/')
        assert normalise(raw,2,2)==[[.6,.8],[0.,1.]]
        assert seen==[('/api/embed','application/json',{'model':'embeddinggemma:300m','input':['doc one','doc two'],
                        'keep_alive':-1,'options':{'num_gpu':0}})]
    finally:
        server.shutdown();thread.join();server.server_close()


@pytest.mark.parametrize('raw,count,dimension',[(None,1,None),([3],1,None),([[1,0]],2,None),
    ([[1,float('inf')]],1,None),([[1,0],[1,0,1]],2,None),([[1,0]],1,3),([[1e308,1e308]],1,None)])
def test_embedding_shape_and_values(raw,count,dimension):
    if raw==[[1e308,1e308]]:
        assert normalise(raw,count,dimension)[0]==pytest.approx([2**-.5,2**-.5])
    else:
        with pytest.raises(ValueError):normalise(raw,count,dimension)


def test_unknown_models_have_no_invented_prefix():
    assert prefixes('unknown-model')==('','')
    assert prefixes('qwen3-embedding:0.6b')[1].startswith('Instruct: ')
