"""Validation command: imports must resolve to this isolated worktree/environment."""
from pathlib import Path
import sys,os,json,hashlib,platform
ROOT=Path(__file__).resolve().parents[1]
import capra,capra.upstream as upstream
from capra import placement_direct_r5,runner_direct_r5,audit_direct_r5,feasibility_direct_r5
import numpy,scipy,cvxpy
record=upstream.import_audit();record['ROOT']=str(upstream.ROOT.resolve())
assert upstream.ROOT.resolve()==ROOT and Path(capra.__file__).resolve().is_relative_to(ROOT)
assert (platform.python_version(),numpy.__version__,scipy.__version__,cvxpy.__version__)==('3.10.10','1.26.4','1.13.1','1.6.5')
assert all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')) and os.environ['PYTHONHASHSEED']=='0'
hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'src/capra').glob('*.py')}
baseline=json.loads((ROOT/'runs/direct_r5/protected_base.json').read_text(encoding='utf8'))
for p,h in baseline.items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,('BASE_CHANGED',p)
out=Path(os.environ['R5_ARTIFACT_DIR']);out.mkdir(parents=True,exist_ok=True)
(out/'environment.json').write_bytes((json.dumps(dict(status='PASS',imports=record,versions=dict(python=platform.python_version(),numpy=numpy.__version__,scipy=scipy.__version__,cvxpy=cvxpy.__version__),source_files_sha256=hashes,protected_files=len(baseline)),ensure_ascii=False,indent=2)+'\n').encode('utf8'))
print('R5_ENVIRONMENT_PASS',len(baseline),'protected files')
