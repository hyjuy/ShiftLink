"""Greetings, thanks and goodbyes on the PDA chat (10/19).

Only exact phrases count: the whole message, with spaces, punctuation and a trailing ㅎ/ㅋ removed, must be one of the
phrases below. Anything else goes to the answer pipeline as before. A message that starts with a greeting and goes on
("안녕 연기가 나요") sends only the rest to the pipeline, so a real report is never answered as small talk.
Embedding and model-based small-talk detection were tested on 10/19 and rejected (rag-v2-log: a greeting in front of a
real problem pulled 9/15 such messages to small talk; the answer model would not call plain small talk small talk).
"""
import re

PHRASES = {
    'greet': ['안녕', '안녕하세요', '안녕하십니까', '안뇽', '하이', 'ㅎㅇ', 'hi', 'hello', '헬로', '반가워', '반가워요', '반갑습니다',
              '좋은 아침', '좋은 아침입니다', '굿모닝'],
    'thanks': ['고마워', '고마워요', '고맙습니다', '감사', '감사해요', '감사합니다', '땡큐', 'thanks', 'thank you'],
    'bye': ['수고', '수고해', '수고하세요', '수고했어', '수고했어요', '수고하셨습니다', '수고 많으셨습니다', '잘 가', '잘 가요', '바이', 'bye',
            '내일 봐', '내일 봐요', '이따 봐', '이따 봐요'],
}
REPLY = {
    'greet': '안녕하세요. 설비 이름과 증상을 적어 주시면 매뉴얼과 지식카드에서 찾아 드릴게요.',
    'thanks': '도움이 됐다니 다행입니다. 다른 증상이 있으면 언제든 물어보세요.',
    'bye': '수고하셨습니다. 안전하게 마무리하세요.',
}
LEAD = {'greet': '안녕하세요. '}   # put in front of the pipeline's answer when the message began with a greeting

_PUNCT = r'[\s!?.,~^·…]'
_EXACT = {re.sub(_PUNCT, '', p.lower()): kind for kind, ps in PHRASES.items() for p in ps}
# leading greeting only (a leading '감사' can mean an audit), then punctuation or space, an optional connective, the rest
_LEAD = re.compile(r'^\s*(' + '|'.join(sorted((r'\s*'.join(map(re.escape, p.split())) for p in PHRASES['greet']),
                                               key=len, reverse=True)) + r')[\sㅎㅋ!?.,~^·…]*[\s!?.,~^·…](?:(?:근데|그런데|그럼|저기|혹시)\s+)?(.*\S.*)$',
                   re.I | re.S)


def _norm(text):
    t = re.sub(_PUNCT, '', text.lower())
    stripped = re.sub(r'[ㅎㅋ]+$', '', t)
    return stripped if len(stripped) >= 2 else t


def classify(question):
    """(kind, rest): kind is 'greet' | 'thanks' | 'bye' | None; rest is the text for the pipeline (None = reply only)."""
    kind = _EXACT.get(_norm(question))
    if kind:
        return kind, None
    m = _LEAD.match(question)
    if m and len(re.sub(_PUNCT, '', m.group(2))) >= 2:
        return _EXACT.get(_norm(m.group(1))), m.group(2).strip()
    return None, question
