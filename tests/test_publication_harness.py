"""Prove the guardrail rejects drift and a bad index blob with a good worktree."""
from pathlib import Path
import os
import re
import runpy
import shutil
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[1]
HARNESS=runpy.run_path(str(ROOT/'scripts/check_knowledge_publication.py'))


def test_publication_harness_matches_current_repository():
    assert HARNESS['check']()==[]


@pytest.fixture
def copied_contract(tmp_path):
    memory=(ROOT/HARNESS['MEMORY']).read_text(encoding='utf-8')
    paths=set(HARNESS['SOURCES'])|{'shiftlink/rag2/generate.py','shiftlink/mes/web/knowledge-candidates.html',
        HARNESS['MEMORY'], HARNESS['HISTORY_CASES'], HARNESS['INTEGRATION_CASES'], HARNESS['NOVEL_CASES'], HARNESS['REAUDIT_CASES'], HARNESS['POSTAUDIT_CASES'], HARNESS['STABILITY_CASES'],
        HARNESS['INSTRUCTIONS'], HARNESS['WORKFLOW']}
    paths.update(re.findall(r'(tests/[\w]+\.py)::test_\w+',memory))
    for path in paths:
        target=tmp_path/path;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/path,target)
    return tmp_path


@pytest.mark.parametrize('damage', ['trigger', 'run', 'scope', 'command', 'integration-trigger', 'integration-run', 'integration-command', 'novel-trigger', 'reaudit-trigger', 'reaudit-command', 'postaudit-trigger', 'postaudit-command'])
def test_history_verification_wiring_cannot_silently_drift(copied_contract, damage):
    target = copied_contract / (HARNESS['WORKFLOW'] if damage in ('trigger', 'run', 'integration-trigger', 'integration-run', 'novel-trigger', 'reaudit-trigger', 'postaudit-trigger') else HARNESS['INSTRUCTIONS'])
    text = target.read_text(encoding='utf-8')
    old = {'trigger': "      - 'tests/test_field_history*.py'",
           'run': 'tests/test_field_history_evaluation.py',
           'scope': 'field_history,', 'command': '--history-scope full',
           'integration-trigger': HARNESS['INTEGRATION_CASES'],
           'integration-run': 'tests/test_field_history_integration.py',
           'integration-command': '--history-scope integration', 'novel-trigger': HARNESS['NOVEL_CASES'],
           'reaudit-trigger':HARNESS['REAUDIT_CASES'], 'reaudit-command':'--history-scope reaudit',
           'postaudit-trigger':HARNESS['POSTAUDIT_CASES'], 'postaudit-command':'--history-scope postaudit'}[damage]
    assert old in text
    target.write_text(text.replace(old, 'missing-history-contract'), encoding='utf-8')
    assert HARNESS['check'](copied_contract, staged=False)


@pytest.mark.parametrize('damage',['model','status','reference'])
def test_drift_check_rejects_broken_contract(copied_contract,damage):
    path={'model':'shiftlink/rag/embedding.py','status':'shiftlink/mes/web/knowledge-candidates.html',
          'reference':HARNESS['MEMORY']}[damage]
    target=copied_contract/path
    original=target.read_text(encoding='utf-8')
    old,new={'model':('embeddinggemma:300m','different-model'),
             'status':('value="quality_passed"','value="obsolete-status"'),
             'reference':('test_draft_changed_without_review_cannot_publish','test_removed_regression')}[damage]
    assert old in original
    target.write_text(original.replace(old,new),encoding='utf-8')
    assert HARNESS['check'](copied_contract,staged=False)


def test_staged_syntax_is_checked_even_when_worktree_is_valid(copied_contract, monkeypatch):
    # Trust only this disposable fixture on filesystems without ownership metadata.
    count = int(os.environ.get('GIT_CONFIG_COUNT', '0'))
    monkeypatch.setenv('GIT_CONFIG_COUNT', str(count + 1))
    monkeypatch.setenv(f'GIT_CONFIG_KEY_{count}', 'safe.directory')
    monkeypatch.setenv(f'GIT_CONFIG_VALUE_{count}', str(copied_contract).replace('\\', '/'))
    subprocess.run(['git','init','--quiet',str(copied_contract)],check=True)
    target=copied_contract/'shiftlink/mes/server.py'
    original=target.read_text(encoding='utf-8')
    target.write_text(original+'\nbroken(\n',encoding='utf-8')
    subprocess.run(['git','add','shiftlink/mes/server.py'],cwd=copied_contract,check=True)
    target.write_text(original,encoding='utf-8')
    assert HARNESS['check'](copied_contract,staged=False)==[]
    assert any('server.py' in error and 'SyntaxError' in error for error in HARNESS['check'](copied_contract,staged=True))
