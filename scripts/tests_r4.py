"""Run original/new tests once, register every actual Job.step inside tests."""
import sys,time,unittest
from r4_utils import DEV,dump
from capra.upstream import Job
original=Job.step;calls=[];attempt=1+len(list(DEV.glob('unit_simulation_calls_*.json')))
def tracked(self,*args,**kwargs):
    start=time.perf_counter()
    try:return original(self,*args,**kwargs)
    finally:calls.append(dict(job=self.name,seconds=args[0] if args else kwargs.get('seconds'),wall_seconds=time.perf_counter()-start,kind='unit_test_Job.step'))
Job.step=tracked
try:
    suite=unittest.defaultTestLoader.discover('tests');result=unittest.TextTestRunner(verbosity=2).run(suite)
finally:
    Job.step=original;dump(DEV/f'unit_simulation_calls_{attempt:02d}.json',calls)
dump(DEV/'unit_tests_receipt.json',dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),job_step_calls=len(calls),calls_file=f'unit_simulation_calls_{attempt:02d}.json'))
sys.exit(0 if result.wasSuccessful() else 1)
