"""Exactly six frozen v2 cells; cumulative budget and audit stop are mandatory."""
from pathlib import Path
from datetime import datetime,timezone
import csv,json,hashlib,time,traceback
from one_cell import execute
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
manifest_path=ROOT/'configs/experiment_manifest_v2.json';m=load(manifest_path);msha=sha(manifest_path)
OUT=ROOT/'runs/capra_v2'/m['version'];ledgerpath=ROOT/'runs/capra_v2/budget_ledger.json'
ledger=load(ledgerpath);ledger['mechanism_validation_reserve_seconds']=60;results=[];blocked=False
def save():
    ledger['used_seconds']=sum(x['wall_seconds'] for x in ledger['experiments'])
    ledger['accounted_seconds']=ledger['used_seconds']+ledger['mechanism_validation_reserve_seconds']
    ledgerpath.write_text(json.dumps(ledger,indent=2)+'\n',encoding='utf8')
    (OUT/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    if results:
        fields=['workload','method','version','status','completed','total','censored','mean_jct','p50_jct','p95_jct','p99_jct','makespan','mean_waiting','mean_training','mean_recovery','decision_median','decision_p95','decision_max','wall_seconds','audit','output']
        with (OUT/'results.csv').open('w',encoding='utf8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(results)
save()
for i,c in enumerate(m['cells'],1):
    assert sha(manifest_path)==msha
    for name,digest in m['files_sha256'].items():assert sha(ROOT/name)==digest,('FROZEN_SOURCE_CHANGED',name)
    for name,digest in m['protected_v1']['sha256'].items():assert sha(ROOT/name)==digest,('V1_CHANGED',name)
    left=m['total_budget_seconds']-ledger['accounted_seconds']
    if blocked or left<=60 or (ROOT/'STOP_REQUEST.json').exists():
        results.append(dict(**c,version=m['version'],status='NOT_RUN',total=80,completed=0,reason='Prior audit failure, user stop or cumulative budget',audit='NOT_RUN'));save();continue
    start=time.perf_counter();process_limit=min(m['process_limit'],left)
    print(json.dumps(dict(event='CELL_START',index=i,total=6,workload=c['workload'],method=c['method'],used_seconds=ledger['used_seconds'],remaining_seconds=left,utc=datetime.now(timezone.utc).isoformat())),flush=True)
    try:
        summary=execute(ROOT/c['input'],c['method'],ROOT/c['output'],['--max-rounds','6000','--wall-limit',str(min(900,max(1,int(process_limit)-60)))],process_limit,'capra.runner_v2','capra.audit_v2')
        if summary is None:
            blocked=True;results.append(dict(**c,version=m['version'],status='FAILED_OR_EXTERNAL_STOP',total=80,completed=None,audit='FAILED'))
        else:
            assert summary['version']==m['version'] and summary['total']==80 and summary['v2_raw_audit']=='PASS'
            results.append(dict(**c,**{k:v for k,v in summary.items() if k not in ('input','method')}))
    except Exception as e:
        blocked=True;results.append(dict(**c,version=m['version'],status='AUDIT_OR_EXECUTION_FAILURE',total=80,completed=None,audit='FAILED',error=repr(e)))
        (OUT/f'failure_cell_{i}.json').write_text(json.dumps(dict(error=repr(e),traceback=traceback.format_exc()),indent=2)+'\n',encoding='utf8')
    finally:
        ledger['experiments'].append(dict(kind='formal',cell=i,workload=c['workload'],method=c['method'],output=c['output'],wall_seconds=time.perf_counter()-start,success=not blocked));save()
    print(json.dumps(dict(event='CELL_END',index=i,status=results[-1]['status'],completed=results[-1]['completed'],mean_jct=results[-1].get('mean_jct'),used_seconds=ledger['used_seconds'],remaining_cells=6-i,errors=blocked)),flush=True)
    if i==3:
        (OUT/'FIRST_WORKLOAD_RESULTS.csv').write_bytes((OUT/'results.csv').read_bytes())
        print('FIRST_WORKLOAD_COMPLETE '+str(OUT/'FIRST_WORKLOAD_RESULTS.csv'),flush=True)
(OUT/'matrix_receipt.json').write_text(json.dumps(dict(status='COMPLETE' if all(r['status']=='ALL_COMPLETE' for r in results) else 'FINISHED_WITH_EXPLICIT_GAPS',cells=len(results),manifest_sha256=msha,budget=ledger,automatic_expansion=False),indent=2)+'\n',encoding='utf8')
print('V2_MATRIX_FINISHED '+str(OUT/'results.csv'),flush=True)
