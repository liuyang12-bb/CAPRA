"""Exactly six A and three B cells, serial, no retries, one preparation deadline."""
import csv,os,sys,traceback
from scenario_control import execute,env
from r2_utils import *
def main():
    os.environ.update(env());cells=load(RUN/'matrix_index.json');receipt=load(RUN/'freeze_receipt.json');assert len(cells)==9
    assert not (RUN/'results.json').exists(),'NO_OVERWRITE_OR_SILENT_RESUME'
    manifests={p:load(ROOT/p) for p in receipt['manifests_sha256']};results=[];blocked=False
    deadline=ledger()['deadline_monotonic']
    def save():
        dump(RUN/'results.json',results)
        fields=['index','phase','phase_version','scenario','method','quota_mode','allocator_mode','status','completed','total','censored','mean_jct','p50_jct','p95_jct','p99_jct','makespan','mean_waiting','mean_training','mean_recovery','decision_median','decision_p95','decision_max','wall_seconds','audit','output','error']
        with (RUN/'results.csv').open('w',encoding='utf8',newline='') as f:
            w=csv.DictWriter(f,fields,extrasaction='ignore');w.writeheader();w.writerows(results)
    for c in cells:
        left=deadline-time.perf_counter()
        if blocked or left<=60 or (ROOT/'STOP_REQUEST.json').exists():
            results.append(dict(**c,status='NOT_RUN',total=80,completed=0,censored=80,audit='NOT_RUN',error='Prior failure, STOP_REQUEST or shared budget'));save();continue
        mp=next(p for p,m in manifests.items() if m['phase']==c['phase']);m=manifests[mp]
        for p,h in receipt['manifests_sha256'].items():assert sha(ROOT/p)==h,('MANIFEST_CHANGED',p)
        for p,h in m['files_sha256'].items():assert sha(ROOT/p)==h,('FROZEN_RUNTIME_CHANGED',p)
        for p,h in m['protected_sha256'].items():assert sha(ROOT/p)==h,('BASE_CHANGED',p)
        print(__import__('json').dumps(dict(event='CELL_START',phase=c['phase'],index=c['index'],total_cells=9,scenario=c['scenario'],method=c['method'],completed=0,total=80,audit='PENDING',elapsed_seconds=time.perf_counter()-ledger()['start_monotonic'],remaining_seconds=left)),flush=True)
        began=time.perf_counter();process_limit=min(960,left-30);runner_limit=min(900,max(1,process_limit-60));out=ROOT/c['output'];process=None
        cmd=[sys.executable,'-X','utf8','-B','-m','capra.runner_r2','--input',c['input'],'--cluster',c['cluster'],'--responses',c['responses'],'--scenario-id',c['scenario'],'--run-version',c['phase_version'],'--allocator-mode',c['allocator_mode'],'--manifest',mp,'--method',c['method'],'--output',str(out),'--interval','60','--max-rounds','6000','--wall-limit',str(runner_limit)]
        try:
            process=execute(cmd,out.parent/(out.name+'.stdout.log'),process_limit,deadline-30)
            if out.exists():dump(out/'process.json',process)
            assert process['exit_code']==0 and not process['external_timeout'] and process['cleanup']['active_after_cleanup']==0,('OWNED_EXECUTION_FAILURE',process)
            from capra.audit_r2 import audit
            summary=audit(out);assert summary['r2_raw_audit']=='PASS' and summary['total']==80
            results.append({**c,**{k:v for k,v in summary.items() if k not in ('method','input','quota_mode','allocator_mode')}})
            if summary['status']!='ALL_COMPLETE':blocked=True
        except Exception as e:
            blocked=True;results.append(dict(**c,status='FORMAL_EXECUTION_OR_AUDIT_FAILURE',total=80,completed=None,censored=None,audit='FAILED',error=repr(e)))
            dump(RUN/f'failure_cell_{c["index"]}.json',dict(error=repr(e),traceback=traceback.format_exc(),process=process))
        finally:
            record('formal',cell=c['index'],phase=c['phase'],scenario=c['scenario'],method=c['method'],status=results[-1]['status'],wall_seconds=time.perf_counter()-began,command=cmd,output=c['output']);save()
        print(__import__('json').dumps(dict(event='CELL_END',phase=c['phase'],index=c['index'],scenario=c['scenario'],method=c['method'],completed=results[-1]['completed'],total=80,status=results[-1]['status'],audit=results[-1]['audit'],mean_jct=results[-1].get('mean_jct'),elapsed_seconds=time.perf_counter()-ledger()['start_monotonic'],remaining_seconds=deadline-time.perf_counter(),errors=blocked)),flush=True)
    elapsed=time.perf_counter()-ledger()['start_monotonic'];dump(RUN/'matrix_receipt.json',dict(status='COMPLETE' if all(r['status']=='ALL_COMPLETE' for r in results) else 'FINISHED_WITH_GAPS',formal_cells=len(results),completed_jobs=sum(r.get('completed') or 0 for r in results),elapsed_seconds=elapsed,shared_budget=ledger(),no_formal_retries=True))
    print('R2_MATRIX_FINISHED',flush=True)
if __name__=='__main__':main()
