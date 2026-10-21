"""Fast publication drift and staged-syntax gate; no models, services or data writes."""
import ast
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ('shiftlink/mes/candidate_review.py','shiftlink/mes/publication.py','shiftlink/mes/query.py',
           'shiftlink/mes/server.py','shiftlink/mes/storage.py','shiftlink/rag/embedding.py',
           'shiftlink/rag2/embed.py','shiftlink/rag2/s30h.py')
MEMORY = 'docs/failures/knowledge-publication-integrity.md'


def literal(root, path, name):
    tree = ast.parse((root/path).read_text(encoding='utf-8'))
    return next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign)
                and any(isinstance(target,ast.Name) and target.id==name for target in node.targets))


def check(root=ROOT, *, staged=True):
    errors=[]
    for path in SOURCES:
        try:
            ast.parse((root/path).read_text(encoding='utf-8'),filename=path)
            if staged:
                result=subprocess.run(['git','show',':'+path],cwd=root,capture_output=True)
                if result.returncode==0:ast.parse(result.stdout.decode('utf-8'),filename='index:'+path)
        except (OSError,SyntaxError,UnicodeError) as error:
            errors.append(f'Python syntax: {path}: {type(error).__name__}')
    try:
        model=literal(root,'shiftlink/rag/embedding.py','PUBLICATION_MODEL')
        if model != literal(root,'shiftlink/rag2/generate.py','CONFIGS')['C']['model']:
            errors.append('Embedding model differs from S30h config C; re-embedding/migration required')
        class Options(HTMLParser):
            def __init__(self):
                super().__init__()
                self.values=set()
            def handle_starttag(self,tag,attrs):
                if tag=='option':self.values.add(dict(attrs).get('value'))
        parser=Options();parser.feed((root/'shiftlink/mes/web/knowledge-candidates.html').read_text(encoding='utf-8'))
        states=set(literal(root,'shiftlink/mes/candidate_review.py','STATUSES').values())|{'pending_review'}
        if states-parser.values:errors.append('MES status filter missing: '+','.join(sorted(states-parser.values)))
        memory=(root/MEMORY).read_text(encoding='utf-8')
        references=re.findall(r'(tests/[\w]+\.py)::(test_\w+)',memory)
        if not references:errors.append('Failure memory has no executable regression references')
        for path,name in references:
            tree=ast.parse((root/path).read_text(encoding='utf-8'))
            if name not in {node.name for node in ast.walk(tree) if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}:
                errors.append(f'Stale regression reference: {path}::{name}')
    except (OSError,SyntaxError,ValueError,KeyError,StopIteration) as error:
        errors.append(f'Drift metadata: {type(error).__name__}: {error}')
    return errors


if __name__=='__main__':
    errors=check()
    print(json.dumps({'ok':not errors,'errors':errors,'staged_python_checked':True},ensure_ascii=False,indent=2))
    sys.exit(bool(errors))
