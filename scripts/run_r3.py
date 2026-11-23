"""Unified validation + 15-cell controller. No automatic formal retries."""
import csv,os,sys,time,traceback,platform,hashlib
from r3_utils import *
from scenario_control import execute,env,Owned
def main():
    os.environ.update(env());bp=RUN/'budget_ledger.json'
    if bp.exists():
        assert '--resume-preparation' in sys.argv and not any(e['kind']=='formal' for e in ledger()['entries']),'NO_BUDGET_RESET_OR_FORMAL_RESUME'
        now=ledger()['start_monotonic'];deadline=ledger()['deadline_monotonic'];check_budget()
    else:
        now=time.perf_counter();deadline=now+7200;dump(bp,dict(start_monotonic=now,deadline_monotonic=deadline,start_utc=datetime.now(timezone.utc).isoformat(),total_budget_seconds=7200,entries=[]))
    results=[];matrix_started=None
    def stage(kind,cmd,limit):
        old=[e for e in ledger()['entries'] if e['kind']==kind]
        if old and old[-1]['status']=='PASS':return old[-1]
        if kind.startswith('smoke_'):assert not old,'TWO_SMOKES_MAX_NO_RETRY'
        attempt=len(old)+1
        check_budget();left=deadline-time.perf_counter();print(__import__('json').dumps(dict(event='STAGE_START',stage=kind,elapsed=7200-left,remaining=left)),flush=True)
        receipt=execute(cmd,DEV/(kind+f'_{attempt:02d}.log'),min(limit,left-30),deadline-30)
        record(kind,attempt=attempt,status='PASS' if receipt['exit_code']==0 and not receipt['external_timeout'] else 'FAILED',**receipt)
        assert receipt['exit_code']==0 and not receipt['external_timeout'],(kind,receipt)
        print(__import__('json').dumps(dict(event='STAGE_PASS',stage=kind,wall=receipt['process_wall_seconds'],remaining=deadline-time.perf_counter())),flush=True)
        return receipt
    def save():
        dump(RUN/'results.json',results)
        fields=['index','phase','phase_version','scenario','profile','method','placement_engine','quota_mode','allocator_mode','executed','result_origin','status','completed','total','censored','mean_jct','p50_jct','p95_jct','p99_jct','makespan','mean_waiting','mean_training','mean_recovery','decision_median','decision_p95','decision_max','wall_seconds','audit','output','error']
        with (RUN/'results.csv').open('w',encoding='utf8',newline='') as f:w=csv.DictWriter(f,fields,extrasaction='ignore');w.writeheader();w.writerows(results)
    try:
        # Environment and protected-byte census run under the same owned global deadline.
        stage('environment',[sys.executable,'-X','utf8','-B','scripts/environment_r3.py'],120)
        stage('tests',[sys.executable,'-X','utf8','-B','scripts/tests_r3.py'],240)
        stage('offline_validation',[sys.executable,'-X','utf8','-B','scripts/validate_r3.py'],360)
        check_budget()
        with (DEV/'owned_tree.log').open('w') as f:
            j=Owned([sys.executable,'-u','-c',"import subprocess,sys,time;subprocess.Popen([sys.executable,'-c','import time;time.sleep(300)']);print('READY',flush=True);time.sleep(300)"],f,env())
            began=time.perf_counter()
            try:
                while 'READY' not in (DEV/'owned_tree.log').read_text() and time.perf_counter()-began<20:check_budget();time.sleep(.05)
                active=j.active()
            finally:cleanup=j.close()
        assert active>=2 and cleanup['active_after_cleanup']==0
        record('owned_tree_validation',status='PASS',descendants=active,wall_seconds=time.perf_counter()-began,cleanup=cleanup)
        for i,(method,profile,mode) in enumerate([('SIA-SMART-P','original','none'),('CAPRA','cm','ram_slack_v1')],1):
            cmd=[sys.executable,'-X','utf8','-B','-m','capra.runner_r3','--input','data/scenarios_r1/w2_dense.csv','--cluster','data/scenarios_r1/cluster_cpu3.json','--responses',f'data/scenarios_r1/responses_{profile}.json','--scenario-id',f'w2_dense_{profile}','--run-version','CAPRA_V2_SMART_R3_PREP','--allocator-mode',mode,'--method',method,'--output',str(DEV/f'smoke_{i:02d}'),'--max-jobs','12','--max-rounds','30','--wall-limit','90']
            receipt=stage(f'smoke_{i:02d}',cmd,120);dump(DEV/f'smoke_{i:02d}/process.json',receipt)
            s=load(DEV/f'smoke_{i:02d}/summary.json');assert s['r3_raw_audit']=='PASS' and s['total']==12 and s['mean_jct'] is None
        stage('audit_rejections',[sys.executable,'-X','utf8','-B','scripts/rejection_r3.py'],120)
        dump(DEV/'validation_receipt.json',dict(status='PASS',tests=load(DEV/'unit_tests_receipt.json'),offline=load(DEV/'offline_validation_receipt.json'),smoke_calls=2,audit_rejections=load(DEV/'audit_rejection_receipt.json')))
        stage('freeze',[sys.executable,'-X','utf8','-B','scripts/freeze_r3.py'],120)
        cells=load(RUN/'matrix_index.json');matrix_started=time.perf_counter();blocked=False
        for c in cells:
            left=deadline-time.perf_counter()
            if blocked or left<=60 or (ROOT/'STOP_REQUEST.json').exists():
                results.append(dict(c,status='NOT_RUN',total=80,completed=0,censored=80,audit='NOT_RUN',error='Prior failure, stop or unified budget'));save();continue
            print(__import__('json').dumps(dict(event='CELL_START',phase=c['phase'],index=c['index'],total_cells=15,scenario=c['scenario'],method=c['method'],completed=0,total=80,audit='PENDING',elapsed_seconds=time.perf_counter()-now,remaining_seconds=left)),flush=True)
            began=time.perf_counter();out=ROOT/c['output'];process=None
            process_limit=min(960,left-30);runner_limit=min(900,max(1,process_limit-60))
            cmd=[sys.executable,'-X','utf8','-B','-m','capra.runner_r3','--input',c['input'],'--cluster',c['cluster'],'--responses',c['responses'],'--scenario-id',c['scenario'],'--run-version',c['phase_version'],'--allocator-mode',c['allocator_mode'],'--manifest',c['manifest'],'--method',c['method'],'--output',str(out),'--interval','60','--max-rounds','6000','--wall-limit',str(runner_limit)]
            try:
                process=execute(cmd,out.parent/(out.name+'.stdout.log'),process_limit,deadline-30)
                if out.exists():dump(out/'process.json',process)
                assert process['exit_code']==0 and not process['external_timeout'] and process['cleanup']['active_after_cleanup']==0,('OWNED_EXECUTION_FAILURE',process)
                s=load(out/'summary.json');assert s['r3_raw_audit']=='PASS' and s['total']==80 and s['status']=='ALL_COMPLETE' and s['completed']==80
                results.append({**c,**{k:v for k,v in s.items() if k not in ('method','input','quota_mode','allocator_mode')},'wall_seconds':process['process_wall_seconds'],'wall_scope':'owned process including imports and independent audit'})
            except Exception as e:
                blocked=True;results.append(dict(c,status='FORMAL_EXECUTION_OR_AUDIT_FAILURE',total=80,completed=load(out/'termination.json')['completed'] if (out/'termination.json').exists() else None,censored=None,audit='FAILED',error=repr(e)))
                dump(RUN/f'failure_cell_{c["index"]}.json',dict(error=repr(e),traceback=traceback.format_exc(),process=process))
            finally:
                record('formal',cell=c['index'],phase=c['phase'],scenario=c['scenario'],method=c['method'],status=results[-1]['status'],wall_seconds=time.perf_counter()-began,command=cmd,output=c['output'],process=process);save()
            print(__import__('json').dumps(dict(event='CELL_END',phase=c['phase'],index=c['index'],scenario=c['scenario'],method=c['method'],completed=results[-1]['completed'],total=80,status=results[-1]['status'],audit=results[-1]['audit'],mean_jct=results[-1].get('mean_jct'),elapsed_seconds=time.perf_counter()-now,remaining_seconds=deadline-time.perf_counter())),flush=True)
            if c['index']==2 and not blocked:
                try:stage('A_smart_semantic_control',[sys.executable,'-X','utf8','-B','scripts/equivalence_r3.py'],120)
                except Exception as e:blocked=True;dump(RUN/'equivalence_gate_failure.json',dict(error=repr(e),traceback=traceback.format_exc()))
        dump(RUN/'matrix_receipt.json',dict(status='COMPLETE' if len(results)==15 and all(r['status']=='ALL_COMPLETE' for r in results) else 'FINISHED_WITH_GAPS',formal_cells=len(results),completed_jobs=sum(r.get('completed') or 0 for r in results),elapsed_seconds=time.perf_counter()-now,matrix_wall_seconds=time.perf_counter()-matrix_started,shared_budget=ledger(),no_formal_retries=True))
    except Exception as e:
        dump(RUN/'preparation_failure.json',dict(error=repr(e),traceback=traceback.format_exc(),elapsed_seconds=time.perf_counter()-now))
        if not results:
            # Full fixed registration is also documented before implementation; no phantom executions.
            dump(RUN/'formal_not_run.json',dict(status='NOT_RUN',physical_cells=15,logical_aliases=4,reason='Preparation failed before freeze',executed_formal=0))
        raise
    finally:
        record('budget_end',status='FINISHED',elapsed_seconds=time.perf_counter()-now)
        dump(RUN/'simulation_calls.json',dict(test_calls=[load(p) for p in sorted(DEV.glob('unit_simulation_calls_*.json'))],process_calls=[e for e in ledger()['entries'] if e['kind'].startswith('smoke_') or e['kind']=='formal'],formal_executed=sum(e['kind']=='formal' for e in ledger()['entries']),smoke_executed=sum(e['kind'].startswith('smoke_') for e in ledger()['entries'])))
    print('R3_MATRIX_FINISHED',flush=True)
if __name__=='__main__':main()
