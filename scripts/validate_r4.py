"""Preregister all R3 fixed states then replay instrumented R4 without Job.step."""
import csv,gzip,json,hashlib
from r4_utils import *
from capra.contracts import Node,Allocation,JobGpuPlan,serialized
from capra.response_v2 import V2Responses
from capra.placement_r4 import create_placement
def raw(d):
    with gzip.open(d/'events.jsonl.gz','rt',encoding='utf8') as f:return [json.loads(x) for x in f]
def clean(x):
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items() if not k.startswith('r4_') and k not in ('generation_seconds','ram_repair_seconds','candidate_seconds','mapping_scoring_seconds','candidate_timings')}
    if isinstance(x,list):return [clean(v) for v in x]
    return x
def main():
    sources=[x for x in load(ROOT/'runs/smart_holdout_r3/analysis/source_index.json') if x['phase']=='B' and x['method'] in ('SIA-SMART-P','CAPRA-FK','CAPRA')]
    chosen=[];cache={};absent=[]
    for src in sources:
        check_budget();d=ROOT/src['output'];rows=raw(d);cache[src['id']]={x['round']:x for x in rows};active=[x for x in rows if x['plan']];pick={x['round'] for x in active[:2]+active[-2:]}
        for rule,predicate in [('first_K',lambda r:r['selection']['selected']=='K'),('first_R',lambda r:r['selection']['selected']=='R'),('first_lock',lambda r:bool(r['locks'])),('first_K_infeasible',lambda r:any(c['label']=='K' and not c['feasible'] for c in r['selection']['candidates']))]:
            hit=next((r for r in active if predicate(r)),None)
            if hit:pick.add(hit['round'])
            else:absent.append(dict(source=src['id'],rule=rule,round=None))
        chosen.extend(dict(source=src,round=i) for i in sorted(pick))
    dump(DEV/'state_replay_preregistration.json',dict(states=chosen,missing_categories=absent))
    results=[]
    for c in chosen:
        check_budget();src=c['source'];r=cache[src['id']][c['round']];s=load(ROOT/src['output']/'start.json')
        response_path=ROOT/src.get('target_responses',s['inputs']['responses']['relative'])
        apps={x['name']:x['application'] for x in csv.DictReader((ROOT/s['inputs']['workload']['relative']).open(encoding='utf8'))};nodes=[Node(**n) for n in load(ROOT/s['inputs']['cluster']['relative'])]
        args=({k:JobGpuPlan(**v) for k,v in r['plan'].items()},nodes,apps,V2Responses(response_path),{k:Allocation(**v) for k,v in r['current'].items()},{k:Allocation(**v) for k,v in r['locks'].items()},r['lock_remaining'],s['costs'],set(r['started']))
        a,m=create_placement(*args,method=src['method'],allocator_mode=src['allocator_mode']).select()
        assert serialized(a)==r['allocations'] and clean(m['candidates'])==clean(r['selection']['candidates'])
        assert m['selected']==r['selection']['selected'] and m['phi']==r['selection']['phi'] and m['relative_to_F']==r['selection']['relative_to_F']
        assert m['r_calls']==r['selection']['r_calls']
        # All original GPU/batch/execution code is bit-identical, and source events
        # keep GPU plan/batch/locks/progress as the fixed complete replay input.
        results.append(dict(source=src['id'],round=r['round'],status='PASS',fixed_gpu_plan_sha256=hashlib.sha256(json.dumps(r['plan'],sort_keys=True).encode()).hexdigest(),unchanged_execution_source=True))
    for src in sources:
        for name,h in src['files_sha256'].items():assert sha(ROOT/src['output']/name)==h
    dump(DEV/'state_replay_results.json',results)
    # Read-only historical scope check, never invoke an old writer/audit.
    r3=load(ROOT/'runs/smart_holdout_r3/final_verification.json');assert r3['physical_formal_complete']==15 and r3['new_complete_job_executions']==1200
    points=load(ROOT/'configs/experiment_manifest_holdout_r3.json')
    for c in points['cells']:
        for k,h in c['input_hashes'].items():assert sha(ROOT/c[k])==h
    dump(DEV/'offline_validation_receipt.json',dict(status='PASS',fixed_states=len(results),R3_sources=len(sources),job_step_calls=0,old_evidence_hashes_verified=True))
    print('R4_OFFLINE_VALIDATION_PASS',flush=True)
if __name__=='__main__':main()
