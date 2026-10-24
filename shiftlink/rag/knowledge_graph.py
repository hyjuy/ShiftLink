"""Query-local ontology graph over the visible KB snapshot; no demo files or inferred causes."""
from collections import Counter, defaultdict
import json

SCHEMA_VERSION = 'shiftlink-retrieval-graph-v1'
# EquipmentType(level=classification) is a card classification, not a physical installed part.
RELATIONS = {'ABOUT': ('CardVersion', 'EquipmentType'),
             'PART_OF': ('EquipmentType', 'EquipmentType'),
             'CITES': ('CardVersion', 'DocumentVersion')}


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _id(kind, *parts):
    return json.dumps([kind, *parts], ensure_ascii=False, separators=(',', ':'))


class KnowledgeGraph:
    """Typed nodes/edges derived only from this query's already-published card view."""

    def __init__(self, cards, eq_type, eq_id):
        self.nodes, self.edges, self.cards = {}, set(), {}
        self.links, self.members = defaultdict(list), defaultdict(list)
        self.locators = defaultdict(list)
        counts = Counter(c.get('card_id') for c in cards)
        for card in cards:
            cid = card.get('card_id')
            if (not eq_type or not _text(cid) or counts[cid] != 1
                    or (card.get('status'), card.get('grade'), card.get('split')) != ('accepted', 'L1', 'kb')
                    or card.get('equipment') not in (eq_type, 'COMMON')
                    or card.get('mes_equipment_id') not in (None, eq_id)
                    or (card.get('mes_equipment_id') is not None and eq_id is None)
                    or not all(_text(card.get(k)) for k in ('version', 'equipment', 'component'))):
                continue
            self.cards[cid] = card
            equipment, component = card['equipment'], card['component']
            cn = self._node('CardVersion', cid, card['version'], card_id=cid, version=card['version'])
            root = self._node('EquipmentType', equipment, equipment=equipment, level='equipment')
            cl = self._node('EquipmentType', equipment, component,
                            equipment=equipment, component=component, level='classification')
            self._edge('PART_OF', cl, root)
            self._link(cid, cn, 'ABOUT', cl)
            for src in (card.get('provenance') or {}).get('sources', []):
                if not all(_text(src.get(k)) for k in ('source_id', 'document_version', 'locator')):
                    continue
                dn = self._node('DocumentVersion', src['source_id'], src['document_version'],
                                source_id=src['source_id'], document_version=src['document_version'])
                self._link(cid, cn, 'CITES', dn)
                if src['locator'] not in self.locators[cn, dn]:
                    self.locators[cn, dn].append(src['locator'])

    def _node(self, kind, *parts, **props):
        ident = _id(kind, *parts)
        self.nodes[ident] = {'id': ident, 'type': kind, **props}
        return ident

    def _edge(self, relation, start, end):
        if (self.nodes[start]['type'], self.nodes[end]['type']) != RELATIONS[relation]:
            raise ValueError('knowledge graph domain/range mismatch')
        self.edges.add((relation, start, end))

    def _link(self, cid, cn, relation, target):
        self._edge(relation, cn, target)
        if (relation, target) not in self.links[cid]:
            self.links[cid].append((relation, target))
            self.members[target].append(cid)

    def summary(self):
        return {'node_counts': {kind: sum(n['type'] == kind for n in self.nodes.values())
                                for kind in ('CardVersion', 'EquipmentType', 'DocumentVersion')},
                'edge_counts': {kind: sum(e[0] == kind for e in self.edges) for kind in RELATIONS}}

    def neighbors(self, seed, candidate_ids):
        """Two-hop classification/citation neighbors, ordered by the caller's dense rank."""
        found = {}
        for relation, target in self.links.get(seed, []):
            for cid in self.members[target]:
                if cid == seed or cid in found:
                    continue
                first, last = self.cards[seed], self.cards[cid]
                start = _id('CardVersion', seed, first['version'])
                end = _id('CardVersion', cid, last['version'])
                found[cid] = {'seed_card_id': seed, 'card_id': cid,
                              'nodes': [self.nodes[start], self.nodes[target], self.nodes[end]],
                              'relations': [relation, relation],
                              'edges': [{'relation': relation, 'from': cn, 'to': target,
                                         **({'locators': list(self.locators[cn, target])} if relation == 'CITES' else {})}
                                        for cn in (start, end)]}
        return [found[cid] for cid in dict.fromkeys(candidate_ids) if cid in found]


def expand_ranking(rows, ranking, cards, eq_type, eq_id, *, top):
    """Retain dense seeds; insert at most two graph neighbors before the existing evidence/judge gates."""
    graph = KnowledgeGraph(cards, eq_type, eq_id)
    trace = {'schema_version': SCHEMA_VERSION, **graph.summary(), 'paths': []}
    baseline = ranking[:top]
    by_card = {}
    for i in ranking:
        meta = rows[i]['metadata']
        cid = meta['source']
        card = graph.cards.get(cid)
        if meta['kind'] != 'card' or not card or meta['folder'] != card['equipment']:
            continue
        # Legacy static chunks have no version. Bind only when the current full know-how is present.
        if 'version' in meta:
            matches = meta['version'] == card['version']
        else:
            matches = _text(card.get('know_how')) and card['know_how'] in rows[i]['text']
        if matches:
            by_card.setdefault(cid, i)
    seeds = list(dict.fromkeys(rows[i]['metadata']['source'] for i in baseline[:8]
                               if by_card.get(rows[i]['metadata']['source']) == i))[:3]
    additions = {}
    for seed in seeds:
        for path in graph.neighbors(seed, list(by_card)):
            cid = path['card_id']
            i = by_card[cid]
            if cid in seeds or i in additions:
                continue
            additions[i] = path
            if len(additions) == 2:
                break
        if len(additions) == 2:
            break
    if not additions:
        return baseline, trace
    merged = []
    for i in baseline:
        if i not in merged:
            merged.append(i)
        if rows[i]['metadata']['source'] in seeds:
            for neighbor in additions:
                if neighbor not in merged:
                    merged.append(neighbor)
            # Insert one bounded graph lane, not one lane per seed.
            break
    merged = list(dict.fromkeys([*merged, *baseline]))[:top]
    trace['paths'] = [{**path, 'chunk_id': rows[i]['chunk_id']} for i, path in additions.items() if i in merged]
    return merged, trace
