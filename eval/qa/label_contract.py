"""Backward-compatible gold sets; a conjunction is never flattened into OR."""


def primary_sets(item):
    return item.get('primary_card_sets', [[cid] for cid in item['primary_card_ids']])


def matches_primary(item, ids):
    cited = set(ids)
    return any(set(group) <= cited for group in primary_sets(item))


def rank1_evaluable(item):
    if item.get('evaluation_status') == 'deferred':
        return False
    return not item['answerable'] or any(len(group) == 1 for group in primary_sets(item))


def validate_label(item, cards):
    """Structural checks only; semantic applicability remains an adjudication task."""
    prefix = item.get('qid', '?')
    def require(condition, message):
        if not condition:
            raise ValueError(f'{prefix}: {message}')
    require(isinstance(item.get('answerable'), bool), 'answerable must be boolean')
    require(item.get('evaluation_status', 'active') in ('active', 'deferred'), 'unknown evaluation_status')
    for field in ('primary_card_ids', 'acceptable_card_ids', 'safety_card_ids', 'key_facts'):
        values = item.get(field)
        require(isinstance(values, list) and all(isinstance(v, str) and v.strip() for v in values), f'invalid {field}')
        require(len(values) == len(set(values)), f'duplicate {field}')
    for field in ('primary_card_ids', 'acceptable_card_ids', 'safety_card_ids'):
        require(set(item[field]) <= cards.keys(), f'unknown card ID in {field}')
    require(not set(item['primary_card_ids']) & set(item['acceptable_card_ids']), 'primary and acceptable overlap')
    require(all(cards[c].get('safety_flag') for c in item['safety_card_ids']), 'non-safety card in safety_card_ids')
    if 'primary_card_sets' in item:
        groups = item['primary_card_sets']
        require(isinstance(groups, list) and bool(groups), 'primary_card_sets must be nonempty')
        for group in groups:
            require(isinstance(group, list) and bool(group) and all(isinstance(c, str) for c in group), 'invalid primary set')
            require(len(group) == len(set(group)), 'duplicate card inside primary set')
        require({cid for group in groups for cid in group} == set(item['primary_card_ids']), 'primary set union differs from primary_card_ids')
    if item.get('evaluation_status') == 'deferred':
        require(not item['primary_card_ids'] and not item['acceptable_card_ids'], 'deferred item has answer gold')
        require(isinstance(item.get('defer_reason'), str) and bool(item['defer_reason'].strip()), 'missing defer_reason')
    else:
        require(bool(item['primary_card_ids']) == item['answerable'], 'active answerability differs from primary gold')
