"""180-minute shared deadline, actual 12-cell serial matrix and recoverable ledger."""
import csv,os,sys,time,traceback
from r4_utils import *
from scenario_control import execute,env,Owned
def main():
    os.environ.update(env());bp=RUN/'budget_ledger.json';resuming=bp.exists()
    if resuming:
        assert '--resume' in sys.argv,'NO_IMPLICIT_BUDGET_RESET_OR_RESUME'
        b=ledger();assert abs((time.time()-time.perf_counter())-b['clock_epoch_estimate'])<30,'MONOTONIC_CLOCK_DOMAIN_CHANGED'
        if b.get('controller_pid')!=os.getpid():
            # On Windows os.kill(pid,0) is not a safe liveness probe.
            import ctypes as C
            from ctypes import wintypes as W
            k=C.WinDLL('kernel32',use_last_error=True)
            k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
            k.GetExitCodeProcess.argtypes=[W.HANDLE,C.POINTER(W.DWORD)];k.CloseHandle.argtypes=[W.HANDLE]
            h=k.OpenProcess(0x1000,False,b['controller_pid'])
            if h:
                code=W.DWORD()
                try:active=bool(k.GetExitCodeProcess(h,C.byref(code))) and code.value==259
                finally:k.CloseHandle(h)
                assert not active,'PRIOR_CONTROLLER_STILL_RUNNING'
        start=b['start_monotonic'];deadline=b['deadline_monotonic'];check_budget();b['controller_pid']=os.getpid();dump(bp,b)
    else:
        start=time.perf_counter();deadline=start+10800;dump(bp,dict(start_monotonic=start,deadline_monotonic=deadline,start_utc=datetime.now(timezone.utc).isoformat(),clock_epoch_estimate=time.time()-start,controller_pid=os.getpid(),total_budget_seconds=10800,entries=[]))
    results=[];matrix_start=None
    def stage(kind,script,limit):
        prior=[e for e in ledger()['entries'] if e['kind']==kind]
        if prior and prior[-1]['status']=='PASS':return prior[-1]
        if kind.startswith('smoke_'):assert not prior,'PREREGISTERED_TWO_SMOKES_ONLY'
        check_budget();attempt=len(prior)+1;left=deadline-time.perf_counter();print(__import__('json').dumps(dict(event='STAGE_START',stage=kind,elapsed_seconds=time.perf_counter()-start,remaining_seconds=left)),flush=True)
        cmd=script if isinstance(script,list) else [sys.executable,'-X','utf8','-B',script]
        receipt=execute(cmd,DEV/f'{kind}_{attempt:02d}.log',min(limit,left-30),deadline-30)
        record(kind,attempt=attempt,status='PASS' if receipt['exit_code']==0 and not receipt['external_timeout'] else 'FAILED',**receipt)
        assert receipt['exit_code']==0 and not receipt['external_timeout'],(kind,receipt)
        print(__import__('json').dumps(dict(event='STAGE_PASS',stage=kind,wall=receipt['process_wall_seconds'],remaining_seconds=deadline-time.perf_counter())),flush=True);return receipt
    def save():
        dump(RUN/'results.json',results)
        fields=['index','scenario','profile','method','display_method','state','status','executed','result_origin','completed','total','submitted','censored','mean_jct','p50_jct','p95_jct','p99_jct','makespan','mean_waiting','mean_training','mean_recovery','decision_median','decision_p95','decision_p99','decision_max','audit_seconds','wall_seconds','audit','output','error']
        with (RUN/'results.csv').open('w',encoding='utf8',newline='') as f:w=csv.DictWriter(f,fields,extrasaction='ignore');w.writeheader();w.writerows(results)
    try:
        if not (RUN/'freeze_receipt.json').exists():
            stage('environment','scripts/environment_r4.py',180)
            stage('tests','scripts/tests_r4.py',240)
            stage('R3_state_replay','scripts/validate_r4.py',360)
            stage('derive_inputs','data/pressure_r4/generate.py',90)
            check_budget()
            if not any(e['kind']=='owned_tree_validation' and e['status']=='PASS' for e in ledger()['entries']):
                with (DEV/'owned_tree.log').open('w') as f:
                    j=Owned([sys.executable,'-u','-c',"import subprocess,sys,time;subprocess.Popen([sys.executable,'-c','import time;time.sleep(300)']);print('READY',flush=True);time.sleep(300)"],f,env());began=time.perf_counter()
                    try:
                        while 'READY' not in (DEV/'owned_tree.log').read_text() and time.perf_counter()-began<20:check_budget();time.sleep(.05)
                        active=j.active()
                    finally:cleanup=j.close()
                assert active>=2 and cleanup['active_after_cleanup']==0;record('owned_tree_validation',status='PASS',descendants=active,cleanup=cleanup)
            for i,(method,profile,mode) in enumerate([('SIA-SMART-P','original','none'),('CAPRA','cm','ram_slack_v1')],1):
                cmd=[sys.executable,'-X','utf8','-B','-m','capra.runner_r4','--input','data/scenarios_r1/w2_dense.csv','--cluster','data/scenarios_r1/cluster_cpu3.json','--responses',f'data/scenarios_r1/responses_{profile}.json','--scenario-id',f'w2_dense_{profile}','--run-version','CAPRA_V2_PRESSURE_R4_PREP','--allocator-mode',mode,'--method',method,'--output',str(DEV/f'smoke_{i:02d}'),'--max-jobs','12','--max-rounds','30','--wall-limit','90']
                receipt=stage(f'smoke_{i:02d}',cmd,120);dump(DEV/f'smoke_{i:02d}/process.json',receipt)
                s=load(DEV/f'smoke_{i:02d}/summary.json');assert s['r4_raw_audit']=='PASS' and s['total']==12 and s['mean_jct'] is None
            stage('closed_loop_control','scripts/smoke_control_r4.py',90)
            stage('audit_rejections','scripts/rejection_r4.py',90)
            dump(DEV/'validation_receipt.json',dict(status='PASS',tests=load(DEV/'unit_tests_receipt.json'),states=load(DEV/'offline_validation_receipt.json'),closed_loop=load(DEV/'closed_loop_control.json'),smoke_calls=2,rejections=load(DEV/'audit_rejection_receipt.json')))
            stage('freeze','scripts/freeze_r4.py',180)
        cells=load(RUN/'matrix_index.json');ml=load(RUN/'matrix_ledger.json');by={x['index']:x for x in ml['cells']};blocked=False;matrix_start=time.perf_counter()
        for c in cells:
            state=by[c['index']];out=ROOT/c['output'];left=deadline-time.perf_counter()
            if state['state']=='COMPLETE_PASS':
                assert resuming
                for name,h in state['final_files_sha256'].items():assert sha(out/name)==h,('RESUME_OUTPUT_CHANGED',name)
                s=load(out/'summary.json');st=load(out/'start.json');assert s['r4_raw_audit']=='PASS' and s['completed']==s['total']==80 and st['manifest_sha256']==c['manifest_sha256'] and st['source_snapshot_sha256']==c['source_snapshot_sha256']
                results.append(dict(c,**{k:v for k,v in s.items() if k not in c},state='COMPLETE_PASS',executed=True,reused_after_resume=True));save();continue
            if state['state']=='RUNNING':
                state.update(state='INCOMPLETE',error='Unclosed execution on resume; no automatic rerun');blocked=True
            if state['state'] in ('FAIL','INCOMPLETE'):blocked=True
            if blocked or left<=60 or (ROOT/'STOP_REQUEST.json').exists():
                state.update(state=state['state'] if state['state'] in ('FAIL','INCOMPLETE') else 'NOT_RUN',error=state.get('error','Earlier failure, STOP_REQUEST or shared budget'))
                results.append(dict(c,state=state['state'],status=state['state'],executed=state.get('executed',False),submitted=80,total=80,completed=state.get('completed',0),censored=80-state.get('completed',0),audit='NOT_RUN',error=state['error']));dump(RUN/'matrix_ledger.json',ml);save();continue
            assert state['state'] in ('CREATED','NOT_RUN') and not out.exists(),'REFUSE_UNDECLARED_OR_OVERWRITE_RUN'
            print(__import__('json').dumps(dict(event='CELL_START',index=c['index'],total_cells=12,scenario=c['scenario'],method=c['display_method'],completed=0,total=80,elapsed_seconds=time.perf_counter()-start,remaining_seconds=left)),flush=True)
            began=time.perf_counter();limit=min(960,left-30);runner_limit=min(900,max(1,limit-60));process=None
            cmd=[sys.executable,'-X','utf8','-B','-m','capra.runner_r4','--input',c['input'],'--cluster',c['cluster'],'--responses',c['responses'],'--scenario-id',c['scenario'],'--run-version','CAPRA_V2_PRESSURE_R4','--allocator-mode',c['allocator_mode'],'--manifest',c['manifest'],'--method',c['method'],'--output',str(out),'--interval','60','--max-rounds','6000','--wall-limit',str(runner_limit)]
            state.update(state='RUNNING',executed=True,start_utc=datetime.now(timezone.utc).isoformat(),start_monotonic=began,command=cmd);dump(RUN/'matrix_ledger.json',ml)
            try:
                process=execute(cmd,out.parent/(out.name+'.stdout.log'),limit,deadline-30)
                if out.exists():dump(out/'process.json',process)
                assert process['exit_code']==0 and not process['external_timeout'] and process['cleanup']['active_after_cleanup']==0,('OWNED_EXECUTION_FAILURE',process)
                s=load(out/'summary.json');assert s['r4_raw_audit']=='PASS' and s['total']==80
                complete=s['status']=='ALL_COMPLETE' and s['completed']==80;actual='COMPLETE_PASS' if complete else 'INCOMPLETE'
                results.append({**c,**{k:v for k,v in s.items() if k not in c},'state':actual,'executed':True,'wall_seconds':process['process_wall_seconds'],'wall_scope':'full owned subprocess including independent audit'})
                state.update(state=actual,completed=s['completed'],final_files_sha256={p.name:sha(p) for p in out.iterdir() if p.is_file()});blocked=not complete
            except Exception as e:
                blocked=True;term=load(out/'termination.json') if (out/'termination.json').exists() else {};done=term.get('completed',0);actual='INCOMPLETE' if process and process['external_timeout'] else 'FAIL'
                state.update(state=actual,completed=done,error=repr(e));results.append(dict(c,state=actual,status=actual,executed=True,submitted=80,total=80,completed=done,censored=80-done,audit='FAILED',error=repr(e),mean_jct=None,p50_jct=None,p95_jct=None,p99_jct=None,makespan=None))
                dump(RUN/f'failure_cell_{c["index"]}.json',dict(error=repr(e),traceback=traceback.format_exc(),process=process))
            finally:
                state.update(end_utc=datetime.now(timezone.utc).isoformat(),end_monotonic=time.perf_counter(),wall_seconds=time.perf_counter()-began,process=process)
                dump(RUN/'matrix_ledger.json',ml);record('formal',cell=c['index'],scenario=c['scenario'],method=c['method'],state=state['state'],wall_seconds=state['wall_seconds'],command=cmd,process=process,output=c['output']);save()
            print(__import__('json').dumps(dict(event='CELL_END',index=c['index'],scenario=c['scenario'],method=c['display_method'],state=state['state'],completed=results[-1]['completed'],total=80,audit=results[-1]['audit'],mean_jct=results[-1].get('mean_jct'),elapsed_seconds=time.perf_counter()-start,remaining_seconds=deadline-time.perf_counter())),flush=True)
        if not blocked:stage('bounded_opportunity_diagnosis','scripts/diagnose_r4.py',900)
        dump(RUN/'matrix_receipt.json',dict(status='COMPLETE' if len(results)==12 and all(x['state']=='COMPLETE_PASS' for x in results) else 'FINISHED_WITH_GAPS',registered_cells=12,physical_executed=sum(x['executed'] for x in results),completed_cells=sum(x['state']=='COMPLETE_PASS' for x in results),completed_jobs=sum(x.get('completed',0) for x in results),elapsed_seconds=time.perf_counter()-start,matrix_wall_seconds=time.perf_counter()-matrix_start,no_formal_retries=True,shared_budget=ledger()))
    except Exception as e:
        attempt=1+len(list(RUN.glob('controller_failure_*.json')));dump(RUN/f'controller_failure_{attempt:02d}.json',dict(error=repr(e),traceback=traceback.format_exc(),elapsed_seconds=time.perf_counter()-start))
        if not (RUN/'matrix_index.json').exists():dump(RUN/'formal_not_run.json',dict(status='NOT_RUN',physical_cells=12,executed_formal=0,reason='Preparation failed before freeze'))
        raise
    finally:
        record('budget_end',status='FINISHED',elapsed_seconds=time.perf_counter()-start)
        dump(RUN/'simulation_calls.json',dict(test_calls=[load(p) for p in sorted(DEV.glob('unit_simulation_calls_*.json'))],process_calls=[e for e in ledger()['entries'] if e['kind'].startswith('smoke_') or e['kind']=='formal'],formal_executed=sum(e['kind']=='formal' for e in ledger()['entries']),smoke_executed=sum(e['kind'].startswith('smoke_') for e in ledger()['entries']),diagnosis_calls=[e for e in ledger()['entries'] if e['kind']=='bounded_opportunity_diagnosis']))
    print('R4_MATRIX_FINISHED',flush=True)
if __name__=='__main__':main()
