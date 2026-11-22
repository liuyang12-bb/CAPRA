"""Persist necessary unit and controlled-mechanism evidence without using main outcomes."""
from pathlib import Path
import contextlib,io,json,sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
import test_contracts as t
out=ROOT/'runs/validation';out.mkdir(parents=True,exist_ok=True)
stream=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromTestCase(t.Contracts)
result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
(out/'contracts_test.log').write_text(stream.getvalue(),encoding='utf8')
assert result.wasSuccessful()
case=t.Contracts();case.setUp()
data={}
for mode in ('fixed','free'):
    allocations,fb=t.allocate(case.plan,case.nodes,case.apps,case.response,mode)
    jobs,events=case.execute(allocations)
    data[mode]=dict(allocations=t.asdict_results(allocations),events=events,fallbacks=fb,
        completion_times={j.name:j.completion_time for j in jobs},mean_jct=sum(j.completion_time for j in jobs)/4,
        raw_training_rate=10,remaining_normalized_work=600,global_batch=128)
data['scope']='Controlled second-stage fixture, not Sia-selected main input and not empirical hardware data.'
(out/'complementarity.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf8')
(out/'contracts_receipt.json').write_text(json.dumps(dict(tests=result.testsRun,passed=result.wasSuccessful(),failures=len(result.failures),errors=len(result.errors)),indent=2)+'\n',encoding='utf8')
print(stream.getvalue());print(json.dumps(data,indent=2))
