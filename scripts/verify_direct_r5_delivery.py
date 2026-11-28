"""Final evidence validation, charged to the same 900s ledger; no new simulation."""
from pathlib import Path
from datetime import datetime,timezone
import os,sys,time,json,hashlib,subprocess,zipfile
from scenario_control import execute
ROOT=Path(__file__).resolve().parents[1];RUN=ROOT/'runs/direct_r5';BP=RUN/'validation_budget.json';BASE='ffa953fb9cd12773992559512d85065bbd26b7b2'
def load(p):return json.loads(Path(p).read_text(encoding='utf8'))
def dump(p,x):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def child(out):
    protected=load(RUN/'protected_base.json');old=Path('D:/科研启航/CAPRA-pressure-opportunity-r4')
    for p,h in protected.items():
        assert sha(ROOT/p)==h,('BASE_CHANGED',p)
        assert sha(old/p)==h,('R4_ORIGINAL_CHANGED',p)
    b=load(BP);successful={}
    for a in b['attempts']:
        if a['kind']=='final_evidence':continue
        successful[a['kind']]=a
        manifest=load(ROOT/a['source_manifest'])
        assert sha(ROOT/manifest['archive'])==manifest['archive_sha256']
        # Earlier attempts retain their own bytes; only the latest applicable tests
        # and the actual smoke runtime must match the delivery source.
        with zipfile.ZipFile(ROOT/manifest['archive']) as z:
            for p,h in manifest['files_sha256'].items():assert hashlib.sha256(z.read(p)).hexdigest()==h
    assert set(successful)=={'environment','tests','smoke1','smoke2'}
    for a in successful.values():
        assert a['status'] in ('PASS','COMPLETE_SMOKE','PARTIAL_SMOKE'),'VALIDATION_FAILURE_OR_INCOMPLETE'
        assert a['process']['cleanup']['active_after_cleanup']==0 and not a['process']['external_timeout']
        assert a['charged_seconds']<=a['outer_hard_limit']
    latest_tests=load(ROOT/successful['tests']['source_manifest'])
    for p,h in latest_tests['files_sha256'].items():assert sha(ROOT/p)==h,('LATEST_TEST_SOURCE_CHANGED',p)
    tests=load(ROOT/successful['tests']['output']/'artifacts/tests_receipt.json');assert tests['status']=='PASS' and not tests['failures'] and not tests['errors']
    artifact=ROOT/successful['tests']['output']/'artifacts'
    replay=load(artifact/'F_replay_results.json');assert replay['total_states']==3 and all(x['status']=='PASS' for x in replay['states'])
    assert load(artifact/'completion_bruteforce.json')['status']=='PASS'
    assert all(x['rejected'] for x in load(artifact/'tamper_rejections.json')['rejections'])
    formal_calls=0;raw={};smokes=[]
    for kind in ('smoke1','smoke2'):
        a=successful[kind];d=ROOT/a['output']/'run';start=load(d/'start.json');summary=load(d/'summary.json')
        assert start['base_commit']==BASE and start['method']=='CAPRA-Direct' and start['max_jobs']==8 and start['max_rounds']==60 and start['wall_limit']==90.
        assert summary['direct_raw_audit']=='PASS' and load(d/'direct_audit.json')['status']=='PASS'
        assert summary['formal_performance_experiment']=='NOT_RUN'
        assert all(summary[k] is None for k in ('mean_jct','p95_jct','p99_jct','makespan')) if summary['completed']<8 else True
        for collection in ('output_hashes.json','audit_hashes.json'):
            for p,h in load(d/collection).items():assert sha(d/p)==h,('RAW_CHANGED',kind,p)
        for k,v in start['inputs'].items():assert sha(ROOT/v['relative'])==v['sha256']
        for p,h in start['source_files_sha256'].items():assert sha(ROOT/p)==h
        raw.update({p.relative_to(ROOT).as_posix():sha(p) for p in d.iterdir() if p.is_file()})
        smokes.append(dict(kind=kind,status=a['status'],rounds=summary['rounds'],completed=summary['completed'],unfinished=summary['unfinished'],output=str(d.relative_to(ROOT)),process_wall_seconds=a['process']['process_wall_seconds']))
    env={k:v for k,v in os.environ.items() if k!='GIT_CONFIG_COUNT' and not k.startswith(('GIT_CONFIG_KEY_','GIT_CONFIG_VALUE_'))}
    def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args],env=env).decode().strip()
    assert git('rev-parse','HEAD')==BASE and git('branch','--show-current')=='capra/direct-placement-r5'
    historical={'main':'1f1f07fd2238b395e108f91dbbc224d07c0c8139','capra/v2-20261122':'0b87934ae558960921889b01d14502155fb0c41c','capra/scenarios-r1':'81b1109ab1124feeac4e846003f4383b39143fc4','capra/ablation-ram-r2':'0876dd916e1b25d2030233826968683da730a55f','capra/smart-holdout-r3':'5af0bdb6b86b797225908f717b5b9324cd48a539','capra/pressure-opportunity-r4':BASE}
    for ref,h in historical.items():assert git('rev-parse',ref)==h
    dump(RUN/'final_evidence_checks.json',dict(status='PASS',base_commit=BASE,protected_files=len(protected),R4_original_tree_preserved=True,historical_refs=historical,tests=tests,smokes=smokes,raw_files_sha256=raw,formal_performance_experiments='NOT_RUN',simulator_or_solver_calls_in_final_check=0,all_prior_owned_cleanup_zero=True))
    print('R5_FINAL_EVIDENCE_PASS',len(protected),'historical files protected')
def main():
    if '--child' in sys.argv:child(Path(sys.argv[-1]));return 0
    b=load(BP);assert all(a['status']!='RUNNING' for a in b['attempts']);used=sum(a.get('charged_seconds',0) for a in b['attempts']);left=900-used
    assert left>=30,'NO_VALIDATION_BUDGET_FOR_FINAL_CHECK'
    kind='tests' if '--targeted-tests' in sys.argv else 'final_evidence'
    previous=[a for a in b['attempts'] if a['kind']==kind];out=RUN/'validation/direct_r5_fixed_validation'/kind/f'attempt{len(previous)+1:02d}'
    assert not out.exists();out.mkdir(parents=True)
    hard=min(left,180.);cmd=[sys.executable,'-X','utf8','-B',__file__,'--child',str(out)]
    extra={}
    if kind=='tests':
        from run_direct_r5_validation import source_hashes
        hashes=source_hashes();fingerprint=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest();archive=RUN/'snapshots'/f'{fingerprint}.zip'
        assert not archive.exists()
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for p in hashes:z.write(ROOT/p,p)
            z.writestr('FILES_SHA256.json',json.dumps(hashes,indent=2))
        dump(out/'source_manifest.json',dict(base_commit=BASE,files_sha256=hashes,source_fingerprint=fingerprint,archive=str(archive.relative_to(ROOT)),archive_sha256=sha(archive)))
        extra=dict(source_fingerprint=fingerprint,source_manifest=str((out/'source_manifest.json').relative_to(ROOT)),reason='Add infeasible/exact-fragmentation coverage; unchanged smoke runtime; no smoke repeat')
        os.environ['R5_ARTIFACT_DIR']=str(out/'artifacts');os.environ['R5_TEST_ARTIFACTS']=str(out/'artifacts');cmd=[sys.executable,'-X','utf8','-B','scripts/tests_direct_r5.py']
    a=dict(kind=kind,index=len(previous)+1,status='RUNNING',outer_hard_limit=hard,command=cmd,output=str(out.relative_to(ROOT)),started_utc=datetime.now(timezone.utc).isoformat(),**extra)
    b['controller_pid']=os.getpid();b['attempts'].append(a);dump(BP,b);began=time.perf_counter()
    try:
        p=execute(cmd,out/'stdout.log',hard-21.);dump(out/'process.json',p)
        a.update(status='EXTERNAL_TIMEOUT' if p['external_timeout'] else ('PASS' if p['exit_code']==0 else 'FAILED'),process=p)
        assert p['cleanup']['active_after_cleanup']==0
    finally:
        a['charged_seconds']=time.perf_counter()-began;a['ended_utc']=datetime.now(timezone.utc).isoformat();b['used_seconds']=sum(x.get('charged_seconds',0) for x in b['attempts']);b['remaining_seconds']=900-b['used_seconds'];dump(BP,b)
    print(json.dumps(dict(status=a['status'],command_wall_seconds=a['charged_seconds'],used_seconds=b['used_seconds'],remaining_seconds=b['remaining_seconds'])),flush=True)
    return 0 if a['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
