"""Budgeted source/input/import/solver checks, never run before execution window."""
from pathlib import Path
import sys,hashlib,platform,os
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from capra.protocol_direct_eval_r6 import *
from capra.upstream import import_audit
from scipy.optimize._highs import _highs_wrapper
import numpy,scipy,cvxpy
def main():
    protected={}
    for p,oid in load(RUN/'base_git_blobs.json')['objects'].items():
        data=(ROOT/p).read_bytes();actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        assert actual==oid,('R5_BASE_BYTES_CHANGED',p);protected[p]=hashlib.sha256(data).hexdigest()
    for p,h in INPUTS.items():assert sha(ROOT/p)==h,('INPUT_BYTES_CHANGED',p)
    for p in INPUTS:
        if p.endswith('.csv'):input_rows(ROOT/p)
    assert (platform.python_version(),numpy.__version__,scipy.__version__,cvxpy.__version__)==('3.10.10','1.26.4','1.13.1','1.6.5')
    assert {k:os.environ.get(k) for k in NUMERIC}==NUMERIC
    imports=import_audit();imports['ROOT']=str(ROOT.resolve())
    hashes=source_files();perf=[p for p in hashes if '/traces/' in p];assert perf,'UPSTREAM_PERFORMANCE_TABLES_NOT_FROZEN'
    environment=dict(python=platform.python_version(),versions=dict(numpy=numpy.__version__,scipy=scipy.__version__,cvxpy=cvxpy.__version__),solver='CVXPY SCIPY/HiGHS, time_limit=10,mip_rel_gap=1e-4,threads=1',highs_wrapper_sha256=sha(_highs_wrapper.__file__),dependency_lock_sha256=sha(ROOT/'requirements_v2.lock.txt'),numeric_environment=NUMERIC,import_audit=imports,actual_environment_prefix=sys.prefix,algorithm_base_commit=BASE,source_files_sha256=hashes,upstream_performance_files=len(perf))
    dump(RUN/'protected_base_sha256.json',protected);dump(RUN/'environment.json',environment)
    print('R6_ENVIRONMENT_PASS',len(protected),'old files;',len(perf),'performance tables')
if __name__=='__main__':main()
