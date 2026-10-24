from pathlib import Path
import sys,unittest,json,dis,types,time,subprocess,hashlib
root=Path(__file__).resolve().parent/'source';sys.path.insert(0,str(root))
targets=[root/'scripts/mes_causal_active_advisory.py',root/'shiftlink/pda/ai_insights.py'];hits={str(p):set() for p in targets}
def trace(frame,event,arg):
 name=frame.f_code.co_filename
 if name not in hits:return None
 if event=='line':hits[name].add(frame.f_lineno)
 return trace
sys.settrace(trace)
from scripts.mes_causal_active_advisory import ActiveAdvisorySource
from tests import test_mes_causal_lifecycle as life
life.Source=ActiveAdvisorySource
names=['tests.test_pda_active_display','tests.test_mes_causal_episode','tests.test_mes_causal_pda_service','tests.test_pda_fault_stop','tests.test_pda_manual_stop','tests.test_pda_advisory_reader','tests.test_mes_causal_context_service','tests.test_analytics_release','tests.test_mes_causal_lifecycle']
suite=unittest.defaultTestLoader.loadTestsFromNames(names);start=time.monotonic();result=unittest.TextTestRunner(verbosity=2).run(suite);sys.settrace(None)
def lines(code):
 out={n for _,n in dis.findlinestarts(code) if n is not None and n>0}
 for v in code.co_consts:
  if isinstance(v,types.CodeType):out|=lines(v)
 return out
(root.parent/'coverage-hits.json').write_text(json.dumps({k:sorted(v) for k,v in hits.items()}))
coverage=[]
for p in targets:
 executable=lines(compile(p.read_text(encoding='utf-8-sig'),str(p),'exec'));seen=hits[str(p)]&executable
 coverage.append(dict(path=str(p.relative_to(root)),covered=len(seen),executable=len(executable),percent=100*len(seen)/len(executable),missing=sorted(executable-seen)))
summary=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),seconds=time.monotonic()-start,coverage=coverage,scope='Pi isolated source; line observation coverage, not branch coverage')
(root.parent/'regression-summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary));raise SystemExit(not result.wasSuccessful())
