"""One preregistered 18-cell matrix, one monotonic preparation+execution deadline."""
from pathlib import Path
from datetime import datetime,timezone
import csv,hashlib,json,sys,time,traceback
from scenario_control import execute
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf8'))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def main():
    manifest=ROOT/'configs/experiment_manifest_scenarios_r1.json';m=load(manifest);msha=sha(manifest)
    ledger=ROOT/'runs/scenarios_r1/budget_ledger.json';b=load(ledger);deadline=b['deadline_monotonic'];out=ROOT/'runs/scenarios_r1'/m['version']
    assert not (out/'results.json').exists(),'NO_OVERWRITE_OR_SILENT_RESUME'
    results=[];blocked=False
    def save():
        b['elapsed_seconds']=time.perf_counter()-b['start_monotonic'];b['remaining_seconds']=max(0,deadline-time.perf_counter());dump(ledger,b)
        dump(out/'results.json',results)
        if results:
            fields=['scenario','method','version','status','completed','total','censored','mean_jct','p50_jct','p95_jct','p99_jct','makespan','mean_waiting','mean_training','mean_recovery','decision_median','decision_p95','decision_max','wall_seconds','audit','output','error']
            with (out/'results.csv').open('w',newline='',encoding='utf8') as f:
                w=csv.DictWriter(f,fields,extrasaction='ignore');w.writeheader();w.writerows(results)
    for i,c in enumerate(m['cells'],1):
        left=deadline-time.perf_counter()
        if blocked or left<=60 or (ROOT/'STOP_REQUEST.json').exists():
            results.append(dict(**c,version=m['version'],status='NOT_RUN',completed=0,total=80,censored=80,audit='NOT_RUN',error='Prior audit/execution failure, STOP_REQUEST or shared deadline'));save();continue
        assert sha(manifest)==msha
        for p,h in m['files_sha256'].items():assert sha(ROOT/p)==h,('FROZEN_CHANGED',p)
        for p,h in m['protected_sha256'].items():assert sha(ROOT/p)==h,('HISTORY_OR_ALGORITHM_CHANGED',p)
        print(json.dumps(dict(event='CELL_START',index=i,total=18,scenario=c['scenario'],method=c['method'],elapsed_seconds=time.perf_counter()-b['start_monotonic'],remaining_seconds=left,utc=datetime.now(timezone.utc).isoformat())),flush=True)
        began=time.perf_counter();process_limit=min(960,left-30);runner_limit=min(900,max(1,process_limit-60));dst=ROOT/c['output']
        cmd=[sys.executable,'-X','utf8','-B','-m','capra.runner_v2','--input',c['input'],'--cluster',c['cluster'],'--responses',c['responses'],'--scenario-id',c['scenario'],'--run-version',m['version'],'--method',c['method'],'--output',str(dst),'--interval','60','--max-rounds','6000','--wall-limit',str(runner_limit)]
        receipt=None
        try:
            receipt=execute(cmd,dst.parent/(dst.name+'.stdout.log'),process_limit,deadline-30)
            if dst.exists():dump(dst/'process.json',receipt)
            assert receipt['exit_code']==0 and not receipt['external_timeout'] and receipt['cleanup']['active_after_cleanup']==0,('EXECUTION_FAILURE',receipt)
            from capra.audit_v2 import audit
            s=audit(dst)
            assert s['v2_raw_audit']=='PASS' and s['total']==80 and s['version']==m['version']
            results.append(dict(**c,**{k:v for k,v in s.items() if k not in ('input','method')}))
            if s['status']!='ALL_COMPLETE':blocked=True
        except Exception as e:
            blocked=True;results.append(dict(**c,version=m['version'],status='AUDIT_OR_EXECUTION_FAILURE',completed=None,total=80,censored=None,audit='FAILED',error=repr(e)))
            dump(out/f'failure_cell_{i}.json',dict(error=repr(e),traceback=traceback.format_exc(),process=receipt))
        finally:
            b['entries'].append(dict(kind='formal',cell=i,scenario=c['scenario'],method=c['method'],wall_seconds=time.perf_counter()-began,status=results[-1]['status'],output=c['output']));save()
        print(json.dumps(dict(event='CELL_END',index=i,scenario=c['scenario'],method=c['method'],status=results[-1]['status'],completed=results[-1]['completed'],mean_jct=results[-1].get('mean_jct'),elapsed_seconds=b['elapsed_seconds'],errors=blocked)),flush=True)
    dump(out/'matrix_receipt.json',dict(status='COMPLETE' if all(r['status']=='ALL_COMPLETE' for r in results) else 'FINISHED_WITH_GAPS',cells=len(results),manifest_sha256=msha,elapsed_seconds=time.perf_counter()-b['start_monotonic'],budget= b,no_expansion=True))
    print('MATRIX_FINISHED',flush=True)
if __name__=='__main__':main()
