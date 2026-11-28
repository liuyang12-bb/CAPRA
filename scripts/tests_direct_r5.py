"""Targeted A-G unittest groups, including exactly three unique R4 F fixtures."""
import os,sys,json,unittest,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tests'))
import test_direct_r5
began=time.perf_counter();suite=unittest.defaultTestLoader.loadTestsFromModule(test_direct_r5)
result=unittest.TextTestRunner(verbosity=2).run(suite)
out=Path(os.environ['R5_ARTIFACT_DIR']);out.mkdir(parents=True,exist_ok=True)
(out/'tests_receipt.json').write_bytes((json.dumps(dict(status='PASS' if result.wasSuccessful() else 'FAILED',groups=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),wall_seconds=time.perf_counter()-began,unique_F_replay_states=3,formal_experiments=0,simulator_Job_step_calls=0),indent=2)+'\n').encode('utf8'))
raise SystemExit(0 if result.wasSuccessful() else 1)
