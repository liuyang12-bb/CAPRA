"""Exactly the frozen six cells, foreground and bounded, with first-workload checkpoint."""
from pathlib import Path
import csv,hashlib,json,sys
from datetime import datetime,timezone
from one_cell import execute
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest_path=ROOT/'configs/experiment_manifest.json'
manifest=json.loads(manifest_path.read_text(encoding='utf8'));manifest_sha=sha(manifest_path)
out=ROOT/'runs/main_v1';out.mkdir(parents=True,exist_ok=True)
results=[]
def write_table():
    rows=[]
    for r in results:
        rows.append({k:r.get(k) for k in ('workload','method','status','completed','total','censored','mean_jct','p95_jct','p99_jct','makespan','decision_median','decision_p95','decision_max','wall_seconds','rounds','audit','output')})
    with (out/'results.csv').open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

failed=False
for i,cell in enumerate(manifest['cells']):
    assert sha(manifest_path)==manifest_sha,'MANIFEST_CHANGED'
    for name,digest in manifest['source_sha256'].items():assert sha(ROOT/name)==digest,('FROZEN_FILE_CHANGED',name)
    assert sha(ROOT/cell['input'])==cell['input_sha256']
    if failed or (ROOT/'STOP_REQUEST.json').exists():
        results.append(dict(**cell,status='NOT_RUN',reason='Prior correctness failure or explicit user stop',completed=0,total=80,audit='NOT_RUN'))
        write_table();continue
    print(json.dumps(dict(status='CELL_START',cell=i+1,total=6,workload=cell['workload'],method=cell['method'],utc=datetime.now(timezone.utc).isoformat())),flush=True)
    summary=execute(ROOT/cell['input'],cell['method'],ROOT/cell['output'],['--interval',str(manifest['interval']),'--max-rounds',str(manifest['max_rounds']),'--wall-limit',str(manifest['runner_wall_limit_seconds'])],manifest['external_process_wall_limit_seconds'])
    if summary is None:
        failed=True
        results.append(dict(**cell,status='FAILED_OR_EXTERNAL_STOP',completed=None,total=80,audit='UNAVAILABLE'))
    else:
        results.append(dict(**cell,**{k:v for k,v in summary.items() if k not in ('input','method')}))
    write_table()
    if i==2:
        (out/'FIRST_WORKLOAD_RESULTS.csv').write_bytes((out/'results.csv').read_bytes())
        print('FIRST_WORKLOAD_COMPLETE '+str(out/'FIRST_WORKLOAD_RESULTS.csv'),flush=True)
(out/'matrix_receipt.json').write_text(json.dumps(dict(status='COMPLETE' if all(r['status']=='ALL_COMPLETE' for r in results) else 'FINISHED_WITH_EXPLICIT_GAPS',manifest_sha256=manifest_sha,cells=len(results),failed=failed,automatic_expansion=False),indent=2)+'\n',encoding='utf8')
print('MATRIX_FINISHED '+str(out/'results.csv'),flush=True)
