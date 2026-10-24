"""Quote reviewed work-log facts after retrieval and judge approval, without rewriting them."""
import re


def is_history_question(question):
    """History needs a certificate: record scope, record fields and no live request.

    A mentioned predicate is shielded only by a local completed-report, reference or
    explicit exclusion suffix. Remaining request predicates are inspected regardless
    of their action root; uncertainty retains the normal MES/model path.
    """
    text = question
    fields = r'순서|시각|시간|담당자|근무자|작업자|결과|근거|이력|대목|문장|내용|문구|단계|결론|확인했다고|기록'
    if not (re.search(r'근무일지|일지|기록|기재|적힌|적었|남긴', text)
            and re.search(fields, text)):
        return False
    time = r'오늘|지금|현재|내일|모레|미래|앞으로|향후|나중에|차주|내주|이번\s*(?:주|교대)|다음\s*(?:해|주|달|작업|교대)'
    quote = r"(?:'[^']*'|\"[^\"]*\"|‘[^’]*’|“[^”]*”)"
    past = r'(?:했던|하였던|했었던|했음(?:이\s*남은)?|했다는|했다고|한|었던|았던|어둔|둔|줬던|받았던|셨던|긴)'
    report = r'(?:기록|문의|질문|판단|확인|검토|요청|지시|적어\s*놓|적|써|메모|요청받|전달|전|부탁|보고|설명|제안|인계|합의|남|말씀하)'
    retrieval = r'(?:알려|말해|보여|찾아|전해|설명해|정리해|요약해|조회해|열람해|읽어|나열해|확인해|답변해|발췌해|제시해|펼쳐|전달해|답해|복사해|옮겨|인용해|가져와|띄워)'
    polite = r'(?:줘(?:요|야|도|서는)?|주(?:세요|십시오|시겠어요|시겠습니까|실래요|시고|시기|시되|시면서|고))'
    completed = r'(?:라고|고)\s*' + report + past + r'(?![가-힣])'
    reference = r'(?:라는\s*)?(?:요청|지시)(?:(?:을|를)\s*받았(?:었)?던|의)'
    exclusion = (r'(?:라는\s*(?:요청|지시)(?:은|는|이)?\s*'
                 r'(?:하지\s*않(?:습니다|겠습니다|을게|았어|는다|아)|아니야|제외(?:해(?:줘)?|합니다))'
                 r'|라고\s*(?:묻|요청하)지\s*않(?:습니다|겠습니다|을게|았어|는다|아))'
                 r'(?![가-힣])')
    # Quote shields require grammatical completion/reference, not mere quote marks.
    text = re.sub(quote + r'\s*(?:' + completed + '|' + reference + ')', ' 이력증명 ', text)
    # Punctuation in unquoted reported speech belongs to that mention only when
    # an explicit quotation particle and completed reporter immediately follow.
    text = re.sub(r'\?(?=\s*라고\s*' + report + past + r'(?![가-힣]))', '', text)
    text = re.sub(r'적힌\s*' + quote + r'\s*(?:요청|지시)의', ' 이력증명 ', text)
    text = re.sub(r'[^\s.!?;\n]+(?:줘서|줘야)\s*'
                  r'(?:(?![.!?;\n]|알려|그리고|대신).)*?'
                  r'(?:했다고|됐다고|끝났다고)\s*기록한', ' 이력증명 ', text)
    # A suffix applies to the immediately preceding mention, never a whole sentence.
    mentioned = r'[^\s.!?;\n]+(?:\s+(?:줘|주세요|주십시오))?'
    text = re.sub(quote + r'\s*' + exclusion, ' 이력증명 ', text)
    # Exclusion belongs to its last mentioned predicate. Keep earlier requests,
    # including an imperative before the mention without punctuation.
    def exclude_mention(match):
        value = match.group()
        mention = re.split(r'라는|라고', value, maxsplit=1)[0]
        predicates = list(re.finditer(r'[가-힣]+?\s*' + polite, mention))
        if predicates:
            prefix = value[:predicates[-1].start()]
            # A single optional time and object belong to the excluded command;
            # other preceding syntax remains visible, including bare predicates.
            if re.fullmatch(r'\s*(?:(?:' + time + r')\s*)?(?:[가-힣0-9]+[을를]\s*)?', prefix):
                return ' 이력증명 '
            return prefix + ' 이력증명 '
        return ' 이력증명 ' if not re.search(r'근무일지|결과|시각', value) else value
    text = re.sub(r'[^.!?;\n]*?' + exclusion, exclude_mention, text)
    # Plain imperatives require the explicit quotation particle -라고. Bare -고
    # also joins independent requests (-주시고), so it cannot certify a mention.
    plain_completed = r'라고\s*' + report + past + r'(?![가-힣])'
    history_intro = r'(?:과거\s*)?근무일지(?:에서|에|의)?\s*'
    def report_unit(match):
        span = match.group()
        remaining = re.sub(mentioned + r'\s*' + plain_completed, ' 이력증명 ', span)
        if re.search(r'[가-힣]+?\s*' + polite + r'|부탁(?:드|해)', remaining):
            return span
        return '근무일지 이력증명 '
    # Reported content and its time belong together; a preceding live predicate
    # cannot borrow the later reporter's completed tense.
    text = re.sub(history_intro + r'(?:(?![.!?;\n]|그리고|대신).)*?'
                  r'(?:라고|고)\s*' + report + past + r'(?![가-힣])', report_unit, text)
    text = re.sub(mentioned + r'\s*(?:' + plain_completed + '|' + reference + ')', ' 이력증명 ', text)
    # Current judgement excluded explicitly is not an independent request.
    def exclude_judgement(match):
        span = match.group()
        if re.search(r'[가-힣]+?\s*' + polite, span):
            return span
        head = re.sub(r'(?:(?:묻|질문하)지\s*않(?:아|습니다|겠습니다)|'
                      r'판단하지\s*말고|말고|아니라|부탁하는\s*것은\s*아닙니다)[,\s]*$', '', span)
        # Nominal requests and connected predicates also precede exclusions;
        # preserving them must not depend on the particular operation verb.
        if re.search(r'[가-힣]+(?:요|다|줘|해|고|며|되)(?:\s+|,)', head):
            return span
        return ' 이력증명 '
    text = re.sub(r'(?:' + time + r')[^.!?;\n]*?(?:(?:묻|질문하)지\s*않(?:아|습니다|겠습니다)|판단하지\s*말고)(?![가-힣])', exclude_judgement, text)
    text = re.sub(r'(?:(?![.!?;\n]|근무일지|이력증명).)*?(?:새\s*)?(?:요청을|지시를)\s*부탁하는\s*것은\s*아닙니다(?![가-힣])', exclude_judgement, text)
    text = re.sub(r'^현재[^.!?;\n]*?(?:말고|아니라)[,\s]*', exclude_judgement, text)
    # Creation time / the selected log describe the record, not a new operation.
    text = re.sub(r'오늘\s*(?:작성|기록|등록|저장)(?:한|했던)\s*(?=근무일지)', '', text)
    text = re.sub(r'이번\s*(?=근무일지)', '', text)
    text = re.sub(r'오늘\s*근무일지', '근무일지', text)
    # Completed events, including causal/obligation morphology, are record content.
    completed_event = (r'(?:(?![.!?;\n]|알려(?!줬던)|말해|보여|그리고|대신).)*?'
                       r'(?:[가-힣]*던|했음|준|된|한|했다는|끝났다는|했다고)'
                       r'\s*(?:(?:작업|조치)의\s*|(?:판단|확인|검토)\s*)?'
                       r'(?:결과|근거|기록|시각|담당자|근무자|순서)')
    # Do not certify a future result target (e.g. 해결된 결과가 되게 해줘).
    def certify_event(match):
        span = match.group()
        # Completion cannot consume an independent imperative. Causal/obligation
        # morphology is inert only inside this already completed event span.
        remainder = re.sub(r'줘(?:서(?!는)|야\s*(?=했|하였))', '', span)
        if re.search(r'[가-힣]+?\s*' + polite, remainder):
            return span
        if re.search(time, span) and not re.search(r'과거|던|했다는|했다고', span):
            return span
        if re.search(r'[가-힣]+할\s*(?:적절한|알맞은)\s*(?:시각|시간)',span):
            return span
        return '근무일지 결과'
    # An achieved target followed by an explicit past event belongs to that event;
    # the same target with a live connective/request must remain judgement.
    event_body = r'(?:(?![.!?;\n]|그리고|대신).)*?'
    text = re.sub(history_intro + event_body + r'(?:되도록|나오게)' + event_body
                  + r'[가-힣]*던\s*(?:시각|결과|기록|순서)', certify_event, text)
    text = re.sub(history_intro + completed_event, certify_event, text)
    # An explicit past-time modifier can bind a second sentence's recorded
    # decision/reason without borrowing the first sentence's result certificate.
    past_reason = (r'당시(?:(?![.!?;\n]|그리고|대신).)*?'
                   r'(?:판단|확인|검토)(?:했던|하였던|했었던|한)\s*(?:결과|근거)')
    text = re.sub(past_reason, certify_event, text)
    text = re.sub(r'(?:(?![.!?;\n]|그리고|대신).)*?했다는\s*설명은\s*'
                  r'당시\s*기록의\s*인용(?:이야|입니다)', certify_event, text)
    # Explicitly completed reports and exclusions certify only their own clause.
    def context_value(lead, span, original):
        remaining = re.sub(r'[가-힣]+\s*달라는|[가-힣]+해줘서', '', span)
        if re.search(r'[가-힣]+?\s*' + polite + r'|부탁(?:드|해)'
                     r'|[가-힣]+(?:해|시켜|하라)(?=\s|,|$)', remaining):
            return original
        return lead + ' 이력증명 '
    def context_clause(match):
        return context_value(match[1], match[2], match.group())
    # A destination certifies its own context, never an earlier independent request.
    text = re.sub(r'(^|[.!?;\n])([^.!?;\n]*?(?:교육\s*자료|감사\s*자료|인수인계)'
                  r'[^.!?;\n]*?(?:거라서|하려고\s*하니|쓰려고요))[,\s]*', context_clause, text)
    text = re.sub(r'(^|[.!?;\n])([^.!?;\n]*?(?:뜻은\s*아니고|'
                  r'(?:지시|권고|문장|판단)(?:은|는|을|를)\s*(?:빼고|생략하고)|'
                  r'새\s*작업\s*지시를\s*내리지\s*말고|새로\s*요약하지\s*말고|말이\s*있어도))[,\s]*', context_clause, text)
    text = re.sub(r'(^|[.!?;\n])([^.!?;\n]*?(?:확인했습니다|마쳤대|끝났어))(?![가-힣])', context_clause, text)
    text = re.sub(r'(^|[.!?;\n])([^.!?;\n]*?(?:했다는|적어\s*둔))(?=\s*근무일지)', context_clause, text)
    # A completed/disclaimed task and the reader's own document use are context.
    # Certify one bounded clause only; context_clause retains preceding requests.
    text = re.sub(r'(^|[.!?;\n])([^.!?;\n]*?(?:끝냈어|받았어|철회했으니|뜻은\s*아닙니다|'
                  r'계산은\s*내가\s*할게|인용할\s*문구를\s*찾고\s*있어|판단을\s*덧붙이지\s*않을\s*거야|'
                  r'회의에서\s*검토할\s*예정이니|인계할\s*때\s*참고하려고\s*하는데|뜻은\s*아니야))[,\s]*', context_clause, text)
    text = re.sub(r'(^|[.!?;\n])([^.!?;\n]*?(?:인계\s*자료|교육\s*자료|교대\s*자료)'
                  r'[^.!?;\n]*?(?:붙일\s*거야|붙여\s*넣을\s*거예요|붙여\s*넣으려니|쓸\s*예정입니다))[,\s]*', context_clause, text)
    # Reading/copying capability applies to the document, not plant operation.
    text = re.sub(r'(?:다음\s*교대\s*자료에\s*붙일|인계\s*자료에\s*붙일\s*수\s*있게|'
                  r'원문\s*그대로\s*받아\s*적을\s*수\s*있게|그대로\s*옮길\s*수\s*있도록)', '', text)
    text = re.sub(r'(?:재)?(?:해석|분석)하지\s*말고|한\s*글자도\s*바꾸지\s*말고', '', text)
    text = re.sub(r'(?:재)?(?:해석|분석)하지\s*말아줘', '원문 읽어줘', text)
    text = re.sub(r'(^|[.!?;\n])(근무일지[^.!?;\n]*?대목을\s*찾았어)', context_clause, text)
    # Document need is the reader's purpose, not an equipment recommendation.
    def copy_need(match):
        lead, span = match[1], match[2]
        remaining = re.sub(r'(?:참고할|인용할|붙일)\s*(?:사본|원문|자료)(?:이|가)\s*필요해$', '', span)
        return context_value(lead, remaining, match.group())
    text = re.sub(r'(^|[.!?;\n])([^.!?;\n]*?(?:참고할|인용할|붙일)\s*'
                  r'(?:사본|원문|자료)(?:이|가)\s*필요해)(?![가-힣])', copy_need, text)
    text = re.sub(r'^가능하시면\s*(?=근무일지)', '', text)
    text = re.sub(r'(근무일지\s*기록을)\s*확인하려고\s*해', r'\1 확인해줘', text)
    # An unrelated leading predicate cannot borrow a later record's certificate.
    # After local mention/exclusion removal, only record modifiers may precede
    # a record anchor in the same clause.
    for clause in re.split(r'(?<!\d)[.!?;\n]+|그리고|대신', text):
        anchor = re.search(history_intro, clause)
        if anchor:
            raw_prefix = clause[:anchor.start()]
            prefix = re.sub(r'이력증명|과거|이전|지난|오늘|당시|검수된|먼저|[,\s]', '', raw_prefix)
            if prefix and not ((re.search(r'(?:적힌|기록된|남긴|기재된)$', prefix)
                                or ('이력증명' in raw_prefix and re.search(fields,prefix)))
                               and not re.search(time + r'|' + polite, prefix)):
                return False
    # Nominal historic judgement results are completed only absent a live time.
    if not re.search(time, text):
        text = re.sub(r'(?:가능(?:한지|할지|한가|해)|가능\s*여부|할\s*수\s*있[^\s]*)'
                      r'\s*(?:를|을)?\s*(?:판단|확인|검토)\s*(?:결과|근거)', '결과', text)
    # Literal transcription is copying only when the original-text purpose is explicit.
    text = re.sub(r'(원문(?:으로|\s*그대로))\s*옮겨(?=\s*' + polite + r')',
                  r'\1 복사해', text)
    # Normalize only record-reading morphology, before testing live capability.
    text = re.sub('(' + retrieval + r')\s*줄\s*(?:래(?:요)?|수\s*있(?:어|어요|나요))', r'\1줘', text)
    text = re.sub('(' + retrieval + r')\s*주실\s*수\s*있(?:나요|어요|어)', r'\1줘', text)
    text = re.sub('(' + retrieval + r')\s*주실\s*수\s*있겠습니까(?![가-힣])', r'\1줘', text)
    text = re.sub(r'조회할\s*수\s*있나요|열람해도\s*될까요', '조회해줘', text)
    # These capability forms ask to read recorded fields, not operate equipment.
    text = re.sub(r'읽어\s*주실\s*수\s*있습니까(?![가-힣])', '읽어줘', text)
    text = re.sub('(' + fields + r')[을를]\s*볼\s*수\s*있을까요(?![가-힣])',
                  r'\1 알려줘', text)
    text = re.sub(r'원문[을를](?:\s*(?:확인용으로|다시))*\s*볼\s*수\s*있을까요(?![가-힣])', '원문 알려줘', text)
    text = re.sub(r'확인하고\s*싶(?:습니다|어요|어)', '확인해줘', text)
    text = re.sub(r'원문으로\s*부탁드[가-힣]+', '원문으로 알려줘', text)
    text = re.sub(r'원문만\s*부탁합니다', '원문만 알려줘', text)
    text = re.sub(r'옮겨\s*적어', '복사해', text)
    text = re.sub(r'열람하고\s*싶(?:습니다|어요|어)', '열람해줘', text)
    text = re.sub(r'(내용)(?:은|는)?\s*어떻게\s*되어\s*있습니까', r'\1 알려줘', text)
    text = re.sub('(' + fields + r')(?:이|가|은|는)?\s*'
                  r'(?:뭐였|언제였|누구였|어떠했)(?:나요|어|어요)', r'\1 알려줘', text)
    text = re.sub('(' + fields + r')(?:이|가)?\s*궁금해', r'\1 알려줘', text)
    # A calculation already written in the record is an object; a requested
    # calculated value without this local modifier still needs fresh judgement.
    text = re.sub(r'(적힌|기록된|기재된)\s*계산한\s*값', r'\1 기록값', text)
    # Any unshielded present/future judgement object stays on MAIN's path.
    if re.search(time + r'|안전|가능|허용|[가-힣]+\s*수\s*있|도\s*되|해도|해야|할까요|방법|추천|제조사|품번|정격|판단해|평가해'
                 r'|계획|예정|예약|일정|(?:필요한\s*)?새\s*(?:조치|절차|작업)|다음\s*절차'
                 r'|되도록|(?:결과|상태)가\s*(?:되게|나오게)'
                 r'|[가-힣]+려면|(?:계산|대조|비교|배정|배분|선정|분석|해석)(?:해|하|한\s*값)'
                 r'|담당자별\s*할\s*일|다시\s*정(?:해|하)'
                 r'|담당자[^.!?;\n]*정해서'
                 r'|[가-힣]+할\s*(?:적절한|알맞은)\s*(?:시각|시간)', text):
        return False
    derived = re.split(r'바탕으로|보고|읽고|토대로|참고해서',text)[-1]
    if derived != text and re.search(r'개선안|대안|방안|할\s*일|견해|의견',derived) and not re.search(r'기록(?:했던|된)|남긴|적힌',derived):
        return False
    if '인수인계문' in text and not re.search(r'원문|그대로',text):
        return False
    # Predicate morphology rather than action-root enumeration protects unknown verbs.
    request = r'([가-힣]+?)\s*' + polite
    for m in re.finditer(request, text):
        if not re.fullmatch(retrieval, m[1]):
            return False
        if m[1] == '확인해':
            # Confirm recorded fields, not an equipment condition inferred from them.
            target = re.split(r'[.!?;\n]|보고|읽고|알려주고|보여주고|그리고|대신', text[:m.start()])[-1]
            if not re.search(fields, target):
                return False
    # Bare polite/imperative forms also require a retrieval predicate certificate.
    residue = re.sub(retrieval + r'\s*(?:' + polite + r'|)(?![가-힣])', '', text)
    if re.search(r'[가-힣]+(?:해|시켜|하라|세요|십시오|겠어요)(?![가-힣])', residue):
        return False
    # Every independent clause must end in retrieval, a record field question or
    # a proved reference/exclusion; unknown final predicates retain MAIN judgement.
    for clause in re.split(r'(?<!\d)[.!?;\n]+|그리고|대신', text):
        clause = clause.strip()
        if not clause:
            continue
        if clause.endswith('이력증명') and re.sub(r'이력증명|[,\s]', '', clause):
            return False
        if not re.search(r'(?:이력증명|' + fields + r')(?:만|은|는)?$'
                         r'|' + retrieval + r'\s*(?:' + polite + r'|)$', clause):
            return False
    return True


def _duration_tokens(text):
    # Compare complete minute values, never a suffix such as 37 in 137 or 0.137.
    return {re.sub(r'[\s,]', '', token) for token in
            re.findall(r'(?<![\d.,])\d+(?:,\d{3})*(?:\.\d+)?\s*분', text)}


def record_sources(question, evidence, cards, equipment_id):
    """Only a judge-kept field chunk can select its immutable, reviewed card as a history source.

    The full record preserves steps crossing chunk boundaries. It is a per-query source view;
    neither stored chunks nor their embeddings are changed.
    """
    by_id = {card['card_id']: card for card in cards}
    durations = _duration_tokens(question)
    dates = re.findall(r'\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2})?', question)
    selected, seen = [], set()
    for row in evidence:
        cid = row['metadata']['source']
        card = by_id.get(cid, {})
        if (not row['chunk_id'].startswith('field_') or cid in seen
                or card.get('mes_equipment_id') != equipment_id
                or (card.get('status'), card.get('grade'), card.get('split')) != ('accepted', 'L1', 'kb')
                or card.get('provenance', {}).get('generator') != 'work-report-capture-v1'):
            continue
        text = '\n'.join([card['title'], card['know_how'], card['rationale']])
        if (not durations.issubset(_duration_tokens(text))
                or not all(value in re.sub(r'\s+', '', text) for value in dates)):
            continue
        seen.add(cid)
        selected.append({**row, 'text': text})
    return selected
