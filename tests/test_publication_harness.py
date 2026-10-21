"""Prove the guardrail rejects drift and a bad index blob with a good worktree."""
from pathlib import Path
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
    paths=set(HARNESS['SOURCES'])|{'shiftlink/rag2/generate.py','shiftlink/mes/web/knowledge-candidates.html',HARNESS['MEMORY']}
    paths.update(re.findall(r'(tests/[\w]+\.py)::test_\w+',memory))
    for path in paths:
        target=tmp_path/path;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/path,target)
    return tmp_path


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


def test_staged_syntax_is_checked_even_when_worktree_is_valid(copied_contract):
    subprocess.run(['git','init','--quiet',str(copied_contract)],check=True)
    target=copied_contract/'shiftlink/mes/server.py'
    original=target.read_text(encoding='utf-8')
    target.write_text(original+'\nbroken(\n',encoding='utf-8')
    subprocess.run(['git','add','shiftlink/mes/server.py'],cwd=copied_contract,check=True)
    target.write_text(original,encoding='utf-8')
    assert HARNESS['check'](copied_contract,staged=False)==[]
    assert any('server.py' in error and 'SyntaxError' in error for error in HARNESS['check'](copied_contract,staged=True))
