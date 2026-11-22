"""Recompute results from raw events; no scheduling/optimization is executed here."""
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import csv,gzip,json,hashlib
import numpy as np
from .contracts import Node,JobGpuPlan,Allocation,validate
from .response import Responses

ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def audit(directory):
    directory=Path(directory)
    seals=json.loads((directory/'output_hashes.json').read_text())
    for name,digest in seals.items():assert sha(directory/name)==digest,('OUTPUT_HASH',name)
    start=json.loads((directory/'start.json').read_text(encoding='utf8'))
    assert sha(Path(start['input']))==start['input_sha256']
    assert sha(ROOT/'configs/cluster.json')==start['cluster_sha256']
    assert sha(ROOT/'data/responses.json')==start['responses_sha256']
    nodes=[Node(**r) for r in json.loads((ROOT/'configs/cluster.json').read_text())]
    response=Responses(ROOT/'data/responses.json',start['neutral'])
    rows=list(csv.DictReader(Path(start['input']).open(encoding='utf8',newline='')))
    if start['max_jobs'] is not None:rows=rows[:start['max_jobs']]
    stats={r['name']:dict(job=r['name'],application=r['application'],arrival=float(r['time']),completion=None,waiting=0.0,training=0.0,recovery=0.0,progress=0.0,segments=0) for r in rows}
    overhead=[];fallbacks=Counter();transitions=Counter();node_rows=[];gpu_repairs=0;rounds=0;segment_checks=0
    allocation_integrals={n.id:[0.0,0.0,0.0] for n in nodes}
    with gzip.open(directory/'events.jsonl.gz','rt',encoding='utf8') as f:
        for line in f:
            r=json.loads(line);rounds+=1
            plan={k:JobGpuPlan(**p) for k,p in r['plan'].items()}
            alloc={k:Allocation(**a) for k,a in r['allocations'].items()}
            locks={k:Allocation(**a) for k,a in r['locks'].items()}
            use=validate(plan,alloc,nodes,locks)
            assert use==r['node_usage']
            if plan:overhead.append(r['decision_seconds'])
            gpu_repairs+=len(r['gpu_stage']['repairs'])
            for e in r['fallbacks']:fallbacks[e['reason']]+=1
            for e in r['transitions']:
                transitions[e['kind']]+=1
                if e['kind']=='aux_update':assert e['cost']==0
                if e['kind']=='migration':assert e['old']['node']!=e['new']['node'] and e['cost']>0
            for e in r['executions']:
                s=stats[e['job']]
                assert s['completion'] is None
                assert abs(s['progress']-e['progress_before'])<1e-7
                assert abs(e['end']-e['start']-e['waiting']-e['training']-e['recovery'])<1e-7
                assert e['progress_after']+1e-9>=e['progress_before']
                assert abs(sum(seg['seconds'] for seg in e['segments'])-e['training'])<1e-7
                last=e['progress_before']
                for seg in e['segments']:
                    a=e['allocation'];assert a is not None
                    assert abs(seg['before']-last)<1e-7
                    expected_rho=response.rho(s['application'],a['gpus'],a['cpu'],a['ram'])
                    assert abs(seg['rho']-expected_rho)<1e-9 and abs(a['rho']-expected_rho)<1e-9
                    predicted=seg['raw_rate']*seg['rho']*seg['seconds']
                    residual=seg['after']-seg['before']-predicted
                    tolerance=0.500001*seg['raw_rate']*seg['rho'] if seg['rounding'] else 1e-6
                    assert abs(residual)<=tolerance+1e-6,('RHO_ONCE_PROGRESS',e['job'],seg,residual)
                    last=seg['after'];segment_checks+=1
                assert abs(last-e['progress_after'])<1e-7
                if e['allocation'] is None:assert e['training']==0 and e['recovery']==0
                if e['recovery']>0:assert e['recovery']<=e['end']-e['start']+1e-7
                for k in ('waiting','training','recovery'):s[k]+=e[k]
                s['progress']=e['progress_after'];s['completion']=e['completion_time'];s['segments']+=len(e['segments'])
                if e['allocation']:
                    a=e['allocation'];dur=e['end']-e['start']
                    for i,k in enumerate(('gpus','cpu','ram')):allocation_integrals[a['node']][i]+=a[k]*dur
            node_rows.extend(dict(round=r['round'],time=r['time'],node=n.id,gpus=use[n.id][0],cpu=use[n.id][1],ram=use[n.id][2]) for n in nodes)
    completed=[s for s in stats.values() if s['completion'] is not None]
    for s in stats.values():
        s['jct']=None if s['completion'] is None else s['completion']-s['arrival']
        if s['jct'] is not None:assert abs(s['jct']-s['waiting']-s['training']-s['recovery'])<1e-6,('JCT_ACCOUNTING',s)
    all_done=len(completed)==len(stats)
    jcts=[s['jct'] for s in completed]
    term=json.loads((directory/'termination.json').read_text())
    process=json.loads((directory/'process.json').read_text()) if (directory/'process.json').exists() else None
    summary=dict(method=start['method'],input=start['input'],status=term['status'],total=len(stats),completed=len(completed),censored=len(stats)-len(completed),
        mean_jct=float(np.mean(jcts)) if all_done else None,p95_jct=float(np.quantile(jcts,.95)) if all_done else None,p99_jct=float(np.quantile(jcts,.99)) if all_done else None,
        makespan=max(s['completion'] for s in completed)-min(s['arrival'] for s in stats.values()) if all_done else None,
        decision_median=float(np.median(overhead)) if overhead else 0,decision_p95=float(np.quantile(overhead,.95)) if overhead else 0,decision_max=max(overhead,default=0),
        wall_seconds=process['process_wall_seconds'] if process else term['wall_seconds'],wall_scope='full subprocess including imports' if process else 'runner body; imports excluded',runner_body_wall_seconds=term['wall_seconds'],rounds=rounds,decisions=len(overhead),transitions=dict(transitions),fallbacks=dict(fallbacks),gpu_repairs=gpu_repairs,
        audit='PASS',segment_checks=segment_checks,scheduling_wall_charged_to_simulation=False,node_allocated_resource_seconds=allocation_integrals)
    for name,data in [('per_job.csv',list(stats.values())),('node_resources.csv',node_rows)]:
        if data:
            with (directory/name).open('w',encoding='utf8',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    (directory/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (directory/'audit_hashes.json').write_text(json.dumps({n:sha(directory/n) for n in ('summary.json','per_job.csv','node_resources.csv')},indent=2)+'\n',encoding='utf8')
    return summary

if __name__=='__main__':
    import sys
    print(json.dumps(audit(sys.argv[1]),ensure_ascii=False))
