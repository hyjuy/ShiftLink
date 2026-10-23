"""Pinned-source incremental PDA advisory service; neural runtimes are excluded."""
import hashlib
import json

def config_digest(config):
    return hashlib.sha256(json.dumps(dict(config,config_id='placeholder'),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

class BoundSource:
    def __init__(self, settings, source_config):
        raise NotImplementedError('pinned production source binding is not implemented')

class AdvisorySession:
    def __init__(self, binding, journal):
        raise NotImplementedError('durable advisory session is not implemented')
