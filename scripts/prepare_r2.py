"""Shared budget, bounded validation and at most two registered smoke calls."""
import os,sys,subprocess,time,platform,hashlib
from datetime import datetime,timezone
from r2_utils import *
from scenario_control import execute,env,Owned
def main():
    path=RUN/'budget_ledger.json'
    if not path.exists():
        now=time.perf_counter();dump(path,dict(start_monotonic=now,deadline_monotonic=now+5400,start_utc=datetime.now(timezone.utc).isoformat(),total_budget_seconds=5400,entries=[]))
    os.environ.update(env());deadline=check_budget()
    import numpy,scipy,cvxpy,importlib.metadata
    from scipy.optimize._highs import _highs_wrapper
    pins={'numpy':'1.26.4','scipy':'1.13.1','cvxpy':'1.6.5'}
    versions={k:importlib.metadata.version(k) for k in pins};assert versions==pins
    assert platform.python_version()=='3.10.10'
    original=load(ROOT/'configs/experiment_manifest_scenarios_r1.json');assert sha(ROOT/'requirements_v2.lock.txt')==original['dependency_lock_sha256']
    binary=Path(_highs_wrapper.__file__);old_binary=Path('D:/科研启航/CAPRA-scenarios-r1/.venv')/binary.relative_to(ROOT/'.venv')
    assert sha(binary)==sha(old_binary),'NUMERIC_SOLVER_BINARY_CHANGED'
    environment=dict(python=platform.python_version(),versions=versions,solver='CVXPY SCIPY/HiGHS bundled in SciPy1.13.1; identical vendor binary hash',highs_wrapper_sha256=sha(binary),baseline_highs_wrapper_sha256=sha(old_binary),
        dependency_lock_sha256=sha(ROOT/'requirements_v2.lock.txt'),numeric_environment=original['numeric_environment'],executable=sys.executable,prefix=sys.prefix,base_commit=BASE)
    if (DEV/'environment.json').exists():assert load(DEV/'environment.json')==environment
    else:dump(DEV/'environment.json',environment)
    protected=DEV/'protected_base.json'
    if not protected.exists():
        raw=git('ls-tree','-rz',BASE);paths={x.split(b'\t',1)[1].decode():x.split(b'\t',1)[0].split()[2].decode() for x in raw.split(b'\0') if x}
        for p,h in paths.items():
            b=(ROOT/p).read_bytes();assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==h,('BASE_FILE_CHANGED',p)
        dump(protected,{p:sha(ROOT/p) for p in paths})
    def done(kind):return any(e['kind']==kind and e.get('status')=='PASS' for e in ledger()['entries'])
    def stage(kind,script,limit):
        if done(kind):return
        check_budget();attempt=1+sum(e['kind']==kind for e in ledger()['entries']);log=DEV/f'{kind}_{attempt:02d}.log'
        receipt=execute([sys.executable,'-X','utf8','-B',script],log,min(limit,check_budget()-time.perf_counter()-30),deadline-30)
        record(kind,status='PASS' if receipt['exit_code']==0 else 'FAILED',**receipt)
        assert receipt['exit_code']==0,(kind,str(log))
    stage('tests','scripts/tests_r2.py',240)
    stage('offline_validation','scripts/validate_r2.py',600)
    if not done('owned_tree_validation'):
        with (DEV/'owned_tree.log').open('w') as f:
            job=Owned([sys.executable,'-u','-c',"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time;time.sleep(300)']);print('READY',flush=True);time.sleep(300)"],f,env())
            start=time.perf_counter()
            while 'READY' not in (DEV/'owned_tree.log').read_text() and time.perf_counter()-start<30:time.sleep(.05)
            active=job.active();receipt=job.close()
        assert active>=2 and receipt['active_after_cleanup']==0
        record('owned_tree_validation',status='PASS',wall_seconds=time.perf_counter()-start,descendants=active,**receipt)
    scenarios={x['id']:x for x in load(ROOT/'configs/scenarios_r1.json')['scenarios']}
    for index,(scenario,method,mode,phase) in enumerate([('w2_dense_original','SIA-P-K','none','CAPRA_V2_ABLATION_R2_PREP'),('w2_dense_cm','CAPRA-FK','ram_slack_v1','CAPRA_V2_RAM_R2_PREP')],1):
        kind='smoke_'+str(index)
        if done(kind):continue
        assert not any(e['kind']==kind for e in ledger()['entries']),'NO_SMOKE_RETRY_OVER_TWO_CALLS'
        assert sum(e['kind'].startswith('smoke_') for e in ledger()['entries'])<2
        c=scenarios[scenario];dst=DEV/f'smoke_{index:02d}';assert not dst.exists();check_budget()
        cmd=[sys.executable,'-X','utf8','-B','-m','capra.runner_r2','--input',c['input'],'--cluster',c['cluster'],'--responses',c['responses'],'--scenario-id',scenario,'--run-version',phase,'--allocator-mode',mode,'--method',method,'--output',str(dst),'--max-jobs','12','--max-rounds','30','--wall-limit','90']
        receipt=execute(cmd,DEV/f'smoke_{index:02d}.stdout.log',min(120,check_budget()-time.perf_counter()-30),deadline-30)
        if dst.exists():dump(dst/'process.json',receipt)
        record(kind,status='PASS' if receipt['exit_code']==0 else 'FAILED',scenario=scenario,method=method,**receipt)
        assert receipt['exit_code']==0,(kind,str(dst))
        from capra.audit_r2 import audit
        summary=audit(dst);assert summary['r2_raw_audit']=='PASS' and summary['total']==12
    dump(DEV/'validation_receipt.json',dict(status='PASS',tests=load(DEV/'unit_tests_receipt.json'),offline=load(DEV/'offline_validation_receipt.json'),smoke_calls=2,budget_elapsed_seconds=time.perf_counter()-ledger()['start_monotonic']))
    print('R2_PREPARATION_PASS',flush=True)
if __name__=='__main__':main()
