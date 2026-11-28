"""Serial cumulative 900-second validation budget; reuses existing owned process trees."""
from pathlib import Path
from datetime import datetime,timezone
import os,sys,json,time,hashlib,zipfile,subprocess,ctypes
from scenario_control import execute,env
ROOT=Path(__file__).resolve().parents[1];RUN=ROOT/'runs/direct_r5';RUNID='direct_r5_fixed_validation';OUT=RUN/'validation'/RUNID;BP=RUN/'validation_budget.json'
BASE='ffa953fb9cd12773992559512d85065bbd26b7b2'
def load(p):return json.loads(Path(p).read_text(encoding='utf8'))
def dump(p,x):p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def source_hashes():
    paths=list((ROOT/'src/capra').glob('*.py'))+list((ROOT/'third_party/sia/sia-simulator').glob('*.py'))+list((ROOT/'scripts').glob('*direct_r5.py'))+[ROOT/'tests/test_direct_r5.py',ROOT/'configs/direct_r5_validation.json',ROOT/'requirements_v2.lock.txt']
    paths += [ROOT/p for p in ('data/pressure_r4/saturn7_dense05.csv','data/pressure_r4/saturn8_dense05.csv','data/scenarios_r1/cluster_cpu3.json','data/scenarios_r1/responses_original.json','data/scenarios_r1/responses_cm.json')]
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(paths)}
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if BP.exists():
        b=load(BP);assert '--resume' in sys.argv,'PERSISTENT_BUDGET_REQUIRES_EXPLICIT_RESUME'
        for a in b['attempts']:
            if a['status']=='RUNNING':
                # Never use os.kill(pid,0) on Windows; conservatively charge unclosed commands.
                k=ctypes.WinDLL('kernel32',use_last_error=True);k.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];k.OpenProcess.restype=ctypes.c_void_p
                k.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)];k.CloseHandle.argtypes=[ctypes.c_void_p]
                h=k.OpenProcess(0x1000,False,b['controller_pid'])
                if h:
                    code=ctypes.c_ulong()
                    try:assert k.GetExitCodeProcess(h,ctypes.byref(code)) and code.value!=259,'PRIOR_CONTROLLER_RUNNING'
                    finally:k.CloseHandle(h)
                a.update(status='UNCLOSED_CONSERVATIVE',charged_seconds=a['outer_hard_limit'],error='Prior command closure missing; full allowed wall charged; not passed')
    else:b=dict(total_seconds=900.,budget_kind='CUMULATIVE_COMMAND_ACTUAL_WALL_INCLUDING_OWNED_CLEANUP',created_utc=datetime.now(timezone.utc).isoformat(),attempts=[])
    b['controller_pid']=os.getpid();dump(BP,b)
    def remaining():return max(0.,900-sum(x.get('charged_seconds',0.) for x in b['attempts']))
    def attempt(kind,command,outer=180):
        hashes=source_hashes();fingerprint=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest();previous=[a for a in b['attempts'] if a['kind']==kind]
        if previous and previous[-1]['status'] in ('PASS','COMPLETE_SMOKE','PARTIAL_SMOKE') and previous[-1]['source_fingerprint']==fingerprint:return previous[-1]
        if remaining()<30:
            row=dict(kind=kind,index=len(previous)+1,status='NOT_RUN',charged_seconds=0,reason='Cumulative command budget insufficient',source_fingerprint=fingerprint);b['attempts'].append(row);dump(BP,b);return row
        index=len(previous)+1;case=OUT/kind/f'attempt{index:02d}';assert not case.exists();case.mkdir(parents=True)
        archive=RUN/'snapshots'/f'{fingerprint}.zip';archive.parent.mkdir(exist_ok=True)
        if not archive.exists():
            with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
                for p in hashes:z.write(ROOT/p,p)
                z.writestr('FILES_SHA256.json',json.dumps(hashes,indent=2))
        dump(case/'source_manifest.json',dict(base_commit=BASE,files_sha256=hashes,source_fingerprint=fingerprint,archive=str(archive.relative_to(ROOT)),archive_sha256=sha(archive)))
        hard=min(float(outer),remaining());limit=hard-21.;assert limit>0
        cmd=command(case,limit) if callable(command) else command
        row=dict(kind=kind,index=index,status='RUNNING',started_utc=datetime.now(timezone.utc).isoformat(),outer_hard_limit=hard,process_execution_limit=limit,cleanup_reserved_seconds=21,source_fingerprint=fingerprint,source_manifest=str((case/'source_manifest.json').relative_to(ROOT)),command=cmd,output=str(case.relative_to(ROOT)))
        b['attempts'].append(row);dump(BP,b);began=time.perf_counter()
        print(json.dumps(dict(event='VALIDATION_START',kind=kind,attempt=index,remaining_seconds=remaining(),outer_hard_limit=hard)),flush=True)
        old_art=os.environ.get('R5_ARTIFACT_DIR');old_test=os.environ.get('R5_TEST_ARTIFACTS')
        os.environ['R5_ARTIFACT_DIR']=str(case/'artifacts');os.environ['R5_TEST_ARTIFACTS']=str(case/'artifacts')
        try:
            process=execute(cmd,case/'stdout.log',limit)
            dump(case/'process.json',process)
            state='FAILED'
            if process['external_timeout']:state='EXTERNAL_TIMEOUT'
            elif process['exit_code']==0 and process['cleanup']['active_after_cleanup']==0:
                if kind.startswith('smoke'):
                    summary=load(case/'run/summary.json');assert summary['direct_raw_audit']=='PASS'
                    assert summary['status'] in ('ALL_COMPLETE','ROUND_LIMIT','WALL_LIMIT'),'UNEXPECTED_SMOKE_TERMINATION'
                    state='COMPLETE_SMOKE' if summary['completed']==summary['total'] else 'PARTIAL_SMOKE'
                else:state='PASS'
            row.update(status=state,process=process,charged_seconds=time.perf_counter()-began)
            assert row['charged_seconds']<=hard+1e-6,('OUTER_HARD_LIMIT_EXCEEDED',row['charged_seconds'],hard)
        except Exception as e:
            row.update(status='FAILED',charged_seconds=time.perf_counter()-began,error=repr(e));raise
        finally:
            if old_art is None:os.environ.pop('R5_ARTIFACT_DIR',None)
            else:os.environ['R5_ARTIFACT_DIR']=old_art
            if old_test is None:os.environ.pop('R5_TEST_ARTIFACTS',None)
            else:os.environ['R5_TEST_ARTIFACTS']=old_test
            row['ended_utc']=datetime.now(timezone.utc).isoformat();b['used_seconds']=900-remaining();b['remaining_seconds']=remaining();dump(BP,b)
        print(json.dumps(dict(event='VALIDATION_END',kind=kind,attempt=index,status=row['status'],charged_seconds=row['charged_seconds'],remaining_seconds=remaining())),flush=True)
        return row
    py=[sys.executable,'-X','utf8','-B']
    environment=attempt('environment',py+['scripts/environment_direct_r5.py'],90)
    tests=attempt('tests',py+['scripts/tests_direct_r5.py'],240) if environment['status']=='PASS' else None
    results=[]
    if tests and tests['status']=='PASS':
        for i,(workload,profile) in enumerate([('saturn7_dense05','original'),('saturn8_dense05','cm')],1):
            def command(case,limit,w=workload,p=profile):return py+['-m','capra.runner_direct_r5','--method','CAPRA-Direct','--allocator-mode','ram_slack_v1','--input',f'data/pressure_r4/{w}.csv','--cluster','data/scenarios_r1/cluster_cpu3.json','--responses',f'data/scenarios_r1/responses_{p}.json','--output',str(case/'run'),'--max-jobs','8','--max-rounds','60','--interval','60','--wall-limit',str(min(90.,max(1.,limit-5.)))]
            result=attempt(f'smoke{i}',command,120);results.append(result)
            if result['status'] not in ('COMPLETE_SMOKE','PARTIAL_SMOKE'):break
    status='VALIDATION_COMPLETE' if tests and tests['status']=='PASS' and len(results)==2 and all(r['status'] in ('COMPLETE_SMOKE','PARTIAL_SMOKE') for r in results) else 'VALIDATION_FAILED_OR_INCOMPLETE'
    dump(RUN/'validation_status.json',dict(status=status,tests=None if tests is None else tests['status'],smokes=[dict(kind=r['kind'],status=r['status'],output=r['output']) for r in results],remaining_seconds=remaining(),used_command_wall_seconds=900-remaining(),formal_performance_experiments='NOT_RUN',all_attempts_preserved=True))
    print(status,flush=True)
    return 0 if status=='VALIDATION_COMPLETE' else 1
if __name__=='__main__':raise SystemExit(main())
