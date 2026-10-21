"""Durable reviewed-card delta index. Network work never holds the MES lock."""
from copy import copy
import json
import os
import threading
import time
from uuid import uuid4

from shiftlink.agent.schemas import KnowledgeCard
from shiftlink.edge.ollama import DEFAULT_HOST
from shiftlink.rag.embedding import PUBLICATION_MODEL, normalise, ollama_embed, prefixes
from .candidate_review import content_hash


def chunks_for(artifact):
    text = artifact['embed_text']
    card = artifact['card']
    # Conservative character budget; every segment retains the same card/version reference.
    return [{'chunk_id':f"field_{card['card_id']}_r{artifact['review_revision']}_{index}",
             'text':card['title']+'\n'+text[start:start+600],
             'embed_text':card['title']+'\n'+text[start:start+600],
             'tokens':len(card['title'])+600,
             'metadata':{'kind':'card','source':card['card_id'],'folder':card['equipment'],
                         'page':index+1,'section':None}}
            for index,start in enumerate(range(0,len(text),600))]


class PublicationManager:
    def __init__(self, service):
        self.service = service
        self._working = threading.Lock()
        with service.storage.connection:
            service.storage.connection.execute('CREATE TABLE IF NOT EXISTS knowledge_publications ('
                'draft_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, content_hash TEXT NOT NULL, '
                'model TEXT NOT NULL, payload TEXT NOT NULL, FOREIGN KEY(draft_id) REFERENCES card_drafts(draft_id))')

    def _write_flags(self, draft):
        self.service.storage.connection.execute('UPDATE card_drafts SET review_flags=? WHERE draft_id=?',
            (json.dumps(draft['review_flags'],ensure_ascii=False,allow_nan=False),draft['draft_id']))

    def _claim(self, now):
        with self.service._lock, self.service.storage.connection:
            for item in self.service.storage.list_card_drafts():
                draft = self.service.storage.get_card_draft(item['draft_id'])
                artifact = draft['review_flags'].get('publication',{})
                if draft['status'] != 'quality_passed' or artifact.get('state') not in (
                        'embedding_pending','embedding_failed','embedding_running') or artifact.get('retry_at',0) > now:
                    continue
                artifact.update(state='embedding_running',searchable=False,attempts=artifact.get('attempts',0)+1,
                                retry_at=now+180,attempt_id=uuid4().hex)
                self._write_flags(draft)
                return draft
        return None

    def _current(self, job):
        draft = self.service.storage.get_card_draft(job['draft_id'])
        artifact = draft['review_flags'].get('publication',{}) if draft else {}
        expected = job['review_flags']['publication']
        return draft if (draft and draft['status']=='quality_passed' and draft['revision']==job['revision']
            and artifact.get('attempt_id')==expected['attempt_id']
            and artifact.get('content_hash')==expected['content_hash']
            and artifact.get('state')=='embedding_running') else None

    def process_one(self, *, embedder=None, now=None):
        if not self._working.acquire(blocking=False):
            return False
        now = time.time() if now is None else now
        job = None
        try:
            job = self._claim(now)
            if job is None:
                return False
            artifact = job['review_flags']['publication']
            card = KnowledgeCard.model_validate(artifact['card']).model_dump(mode='json')
            if (content_hash(card) != artifact['content_hash'] or not artifact.get('assets')
                    or artifact['review_revision'] != job['revision']):
                raise ValueError('review artifact integrity mismatch; repeat quality review')
            model = PUBLICATION_MODEL
            doc_prefix, query_prefix = prefixes(model)
            dimension = None
            pipeline = self.service.query_pipeline
            if getattr(pipeline,'answer_mode',None)=='s30h':
                from shiftlink.rag2.s30h import CFG
                if model != CFG['model']:
                    raise ValueError('publication model differs from active search model')
                dimension = int(pipeline.vec.shape[1])
            chunks = chunks_for(artifact)
            raw = (embedder or ollama_embed)([doc_prefix+chunk['embed_text'] for chunk in chunks], model,
                                            os.environ.get('OLLAMA_HOST',DEFAULT_HOST))
            vectors = normalise(raw,len(chunks),dimension)
            manifest = {'model':model,'dimension':len(vectors[0]),'doc_prefix':doc_prefix,'query_prefix':query_prefix,
                        'review_revision':job['revision'],'content_hash':artifact['content_hash'],
                        'assets':artifact['assets'],'format':'reviewed-card-delta-v1'}
            payload = json.dumps({'card':card,'chunks':chunks,'vectors':vectors,'manifest':manifest},
                                 ensure_ascii=False,allow_nan=False)
            with self.service._lock, self.service.storage.connection:
                current = self._current(job)
                if current is not None:
                    self.service.storage.connection.execute('INSERT OR REPLACE INTO knowledge_publications VALUES (?,?,?,?,?)',
                        (job['draft_id'],job['revision'],artifact['content_hash'],model,payload))
                    current['review_flags']['publication'].update(state='published',searchable=True,
                        model=model,dimension=len(vectors[0]),published_at=now,error=None,retry_at=0)
                    self._write_flags(current)
            return True
        except Exception as error:  # A failed job stays durable and is retried, never silently published.
            if job is None:
                raise
            with self.service._lock, self.service.storage.connection:
                current = self._current(job)
                if current is not None:
                    current['review_flags']['publication'].update(state='embedding_failed',searchable=False,
                        error=f'임베딩·검색 저장 실패 ({type(error).__name__}). 자동으로 재시도합니다.',
                        retry_at=now+min(300,5*2**min(6,current['review_flags']['publication']['attempts'])))
                    self._write_flags(current)
            return True
        finally:
            self._working.release()

    def run(self, stopped):
        while not stopped.is_set():
            try:
                worked = self.process_one()
            except Exception as error:
                print(f'[지식카드 게시 작업 오류] {type(error).__name__}',flush=True)
                worked = False
            if stopped.wait(.1 if worked else 2):
                break

    def snapshot(self, pipeline, equipment_id, asset_id, observations):
        """Copy a query's index view; baseline index and other in-flight queries are immutable."""
        from shiftlink.rag.retrieval import InMemoryToolProvider, _condition_status
        if not (isinstance(getattr(pipeline,'tools',None),InMemoryToolProvider)
                or getattr(pipeline,'answer_mode',None)=='s30h'):
            return pipeline, []
        records, ticket = [], []
        observer = InMemoryToolProvider(equipment_db=self.service.catalog.data['equipment'],
                                       equipment_types=self.service.catalog.data['equipment_types'])
        values = {item['signal']:{'value':item['value'],'unit':item.get('unit')} for item in observations}
        values = observer._with_derived_states(observer._resolve_equipment([equipment_id]),values)
        # Called under the MES lock. SQLite commits the row and its visibility flag together.
        for draft_id,revision,digest,model,payload in self.service.storage.connection.execute(
                'SELECT p.* FROM knowledge_publications p JOIN card_drafts d USING(draft_id) '
                "WHERE d.status='quality_passed' AND json_extract(d.review_flags,'$.publication.state')='published'"):
            draft = self.service.storage.get_card_draft(draft_id)
            artifact = draft['review_flags']['publication']
            if (draft['revision'] != revision or artifact.get('content_hash') != digest
                    or not artifact.get('searchable') or artifact.get('assets',{}).get(equipment_id) != asset_id
                    or model != PUBLICATION_MODEL):
                continue
            record = json.loads(payload)
            card = KnowledgeCard.model_validate(record['card'])
            if (content_hash(record['card']) != digest or record['manifest']['content_hash'] != digest
                    or record['manifest']['assets'].get(equipment_id) != asset_id
                    or card.mes_equipment_id not in (None,equipment_id) or _condition_status(card,values) != 'verified'):
                continue
            record['vectors'] = normalise(record['vectors'],len(record['chunks']),record['manifest']['dimension'])
            if getattr(pipeline,'answer_mode',None)=='s30h' and len(record['vectors'][0]) != pipeline.vec.shape[1]:
                continue
            records.append(record)
            ticket.append((draft_id,revision,digest,equipment_id,asset_id))
        if not records:
            return pipeline, []
        view = copy(pipeline)
        if getattr(pipeline,'answer_mode',None)=='s30h':
            import numpy as np
            view.rows = [*pipeline.rows,*(chunk for record in records for chunk in record['chunks'])]
            view.vec = np.vstack([pipeline.vec,*(record['vectors'] for record in records)])
            view.folders = np.array([row['metadata']['folder'] for row in view.rows])
            view.cards = [*pipeline.cards,*(record['card'] for record in records)]
        else:
            view.tools = copy(pipeline.tools)
            view.tools.cards = [*pipeline.tools.cards,*(KnowledgeCard.model_validate(record['card']) for record in records)]
        return view, ticket

    def still_current(self, ticket):
        for draft_id,revision,digest,equipment_id,asset_id in ticket:
            draft = self.service.storage.get_card_draft(draft_id)
            artifact = draft['review_flags'].get('publication',{}) if draft else {}
            current_asset = next((eq.asset_id for eq in self.service.active_config.equipment
                                  if eq.equipment_id==equipment_id),None)
            if (not draft or draft['status']!='quality_passed' or draft['revision']!=revision
                    or artifact.get('state')!='published' or artifact.get('content_hash')!=digest
                    or not artifact.get('searchable') or current_asset!=asset_id):
                return False
        return True
