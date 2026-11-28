from pathlib import Path
import sys,time,unittest,os,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tests'))
import test_direct_eval_r6
began=time.perf_counter();result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_direct_eval_r6))
out=Path(os.environ['R6_VALIDATION_ARTIFACTS']);out.mkdir(parents=True,exist_ok=True)
(out/'tests_receipt.json').write_text(json.dumps(dict(status='PASS' if result.wasSuccessful() else 'FAILED',groups=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),wall_seconds=time.perf_counter()-began,F_only_states=3,real_Job_step_calls=2,new_closed_loop_smokes=0,new_formal_cells=0),indent=2),encoding='utf8')
raise SystemExit(0 if result.wasSuccessful() else 1)
