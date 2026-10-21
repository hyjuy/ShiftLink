"""Shared Ollama embedding contract for batch indexes and reviewed field cards."""
import json
import math
import urllib.request


PUBLICATION_MODEL = 'embeddinggemma:300m'
PREFIX = {
    'embeddinggemma': ('title: none | text: ', 'task: search result | query: '),
    'qwen3-embedding': ('', 'Instruct: Given a maintenance question, retrieve manual passages that answer it\nQuery: '),
}


def prefixes(model):
    return next((value for key, value in PREFIX.items() if model.startswith(key)), ('', ''))


def ollama_embed(texts, model, host):
    request = urllib.request.Request(host.rstrip('/')+'/api/embed',
        data=json.dumps({'model':model,'input':texts,'keep_alive':-1,'options':{'num_gpu':0}}).encode(),
        headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)['embeddings']


def normalise(vectors, count, dimension=None):
    if not isinstance(vectors, list) or len(vectors) != count or not vectors:
        raise ValueError('embedding row count mismatch')
    dimension = dimension or (len(vectors[0]) if isinstance(vectors[0],list) else 0)
    if dimension < 2:
        raise ValueError('invalid embedding dimension')
    result = []
    for vector in vectors:
        if not isinstance(vector,list) or len(vector) != dimension or any(
                type(value) not in (int,float) or not math.isfinite(value) for value in vector):
            raise ValueError('invalid embedding values or dimensions')
        norm = math.hypot(*vector)
        if not norm or not math.isfinite(norm):
            raise ValueError('invalid embedding norm')
        result.append([value/norm for value in vector])
    return result
