"""Preregister then replay a bounded set of R2 states; no Job.step or full GPU simulation."""
import ast,csv,io,json,time,hashlib
from collections import Counter
from r3_utils import *
from equivalence_r3 import control,semantic
from capra.contracts import Node,Allocation,JobGpuPlan,serialized
from capra.response_v2 import V2Responses
from capra.response import Responses
from capra.placement_r3 import create_placement
from capra.methods_r3 import spec,engine
import gzip
def read_events(p):
    with gzip.open(p/'events.jsonl.gz','rt',encoding='utf8') as f:return [json.loads(x) for x in f]
def main():
    # Select all states before running even the first placement replay.
    sources=load(ROOT/'runs/ablation_ram_r2/analysis/source_index.json')
    selected=[];source_rules=[]
    for src in sources:
        if src['phase'] not in ('A','B'):continue
        if src['method'] not in ('SIA-P-K','CAPRA-FK','CAPRA'):continue
        d=ROOT/src['output'];rows=read_events(d);active=[r for r in rows if r['plan']]
        pick={r['round'] for r in active[:2]+active[-2:]}
        for label,predicate in [('first_K',lambda r:r['selection']['selected']=='K'),('first_R',lambda r:r['selection']['selected']=='R'),('first_lock',lambda r:bool(r['locks'])),('first_K_infeasible',lambda r:any(c['label']=='K' and not c['feasible'] for c in r['selection']['candidates']))]:
            hit=next((r for r in active if predicate(r)),None)
            source_rules.append(dict(source=src['id'],rule=label,round=None if hit is None else hit['round']))
            if hit:pick.add(hit['round'])
        selected.extend(dict(source=src,round=r['round']) for r in rows if r['round'] in pick)
    dump(DEV/'state_replay_preregistration.json',dict(states=selected,rules=source_rules))
    results=[];cache={}
    # legacy source states are replayed through unchanged R2 class in new factory;
    # R3 formal contracts forbid legacy, so compatibility fixture explicitly uses old constructor.
    from capra.placement_r2 import PlacementR2
    def clean(x):
        if isinstance(x,dict):return {k:clean(v) for k,v in x.items() if k not in ('generation_seconds','ram_repair_seconds')}
        if isinstance(x,list):return [clean(v) for v in x]
        return x
    for entry in selected:
        check_budget();src=entry['source'];d=ROOT/src['output'];s=load(d/'start.json')
        if src['output'] not in cache:cache[src['output']]={r['round']:r for r in read_events(d)}
        r=cache[src['output']][entry['round']]
        nodes=[Node(**x) for x in load(ROOT/s['inputs']['cluster']['relative'])]
        apps={x['name']:x['application'] for x in csv.DictReader((ROOT/s['inputs']['workload']['relative']).open(encoding='utf8'))}
        args=({k:JobGpuPlan(**v) for k,v in r['plan'].items()},nodes,apps,V2Responses(ROOT/s['inputs']['responses']['relative']),{k:Allocation(**v) for k,v in r['current'].items()},{k:Allocation(**v) for k,v in r['locks'].items()},r['lock_remaining'],s['costs'],set(r['started']))
        mode=src['allocator_mode'];method=src['method']
        p=(create_placement(*args,method=method,allocator_mode=mode) if mode!='legacy' else PlacementR2(*args,method=method,allocator_mode=mode))
        a,m=p.select();assert serialized(a)==r['allocations'];assert clean(m['candidates'])==clean(r['selection']['candidates'])
        assert m['selected']==r['selection']['selected'] and m['relative_to_F']==r['selection']['relative_to_F']
        assert m['r_calls']==r['selection']['r_calls']
        results.append(dict(source=src['id'],round=r['round'],status='PASS',factory_unchanged_class=p.__class__ is PlacementR2))
    dump(DEV/'state_replay_results.json',results)
    # All source evidence hashes in old R2 source-index checked read-only.
    for src in sources:
        check_budget()
        for name,h in src['files_sha256'].items():assert sha(ROOT/src['output']/name)==h
    r2control=control(ROOT/'runs/ablation_ram_r2/CAPRA_V2_ABLATION_R2/w2_dense_original/SIA-P-K',ROOT/'runs/ablation_ram_r2/CAPRA_V2_ABLATION_R2/w2_dense_cm/SIA-P-K',DEV/'r2_pk_control.json')
    nodes=[Node(**n) for n in load(ROOT/'data/scenarios_r1/cluster_cpu3.json')]
    a=V2Responses(ROOT/'data/scenarios_r1/responses_original.json');b=V2Responses(ROOT/'data/scenarios_r1/responses_cm.json');points=[]
    assert a.data['cpu_axis']==b.data['cpu_axis'] and a.data['ram_axis']==b.data['ram_axis']
    for n in nodes:
        assert n.cpu/n.gpus==3 and n.ram/n.gpus==62.5
        for app in ('cifar10','imagenet','bert','deepspeech2'):
            for g in (1,2,4,8):
                if g>n.gpus:continue
                c=n.cpu*g/n.gpus;m=n.ram*g/n.gpus
                assert a.legal(g,c,m,n) and b.legal(g,c,m,n)
                x=a.rho(app,g,c,m);y=b.rho(app,g,c,m);assert x==y==1.,('STRICT_PROP_EQ',app,g,x,y)
                points.append(dict(node=n.id,application=app,gpus=g,cpu=c,ram=m,original_rho=x,CM_rho=y,strict_equal=True))
    dump(DEV/'proportional_points.json',points)
    # Exact inherited code paths are immutable; static call boundaries and test isolation
    # plus full observed quota/rho auditing establish the response-independent execution domain.
    static=dict(status='PASS',placement_original_sha256=sha(ROOT/'src/capra/placement_r2.py'),gpu_original_sha256=sha(ROOT/'src/capra/gpu_stage.py'),quota_path='ProportionalAllocator.baseline -> proportional -> rho only; no preferred/solve/repair',gpu_path='GpuStage.info and lock_constraints do not query responses; choose only proportional validation',induction='Equal initial Job/policy states and exact rho=1 at all reachable proportional points imply same GPU inputs/MIP, same deterministic placement and locks, same commit costs/batch and Job.step progress. Equal next state follows; repeat until all complete. A full smart control and R2 P-K control provide preregistered dynamic checks.',points=len(points),r2_control=r2control)
    dump(DEV/'equivalence_static_certificate.json',static)
    # Generate the previously registered holdout; verify every original field and time.
    old=load(ROOT/'runs/ablation_ram_r2/analysis/next_candidate_inputs.json');derived=[]
    for src in old['candidates']:
        check_budget();p=ROOT/src['source'];assert sha(p)==src['source_sha256']
        with p.open(encoding='utf8',newline='') as f:reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
        eligible=[(i,r) for i,r in enumerate(rows) if r['application'] in ('cifar10','imagenet','bert','deepspeech2') and 1<=int(r['num_replicas'])<=8]
        eligible.sort(key=lambda x:(float(x[1]['time']),x[0]));chosen=eligible[:80];assert len(chosen)==80 and len(eligible)==src['eligible_rows']
        assert [i for i,r in chosen]==src['source_zero_based_indices']
        assert dict(Counter(r['application'] for i,r in chosen))==src['application_counts']
        assert float(chosen[0][1]['time'])==src['first_original_arrival'] and float(chosen[-1][1]['time'])==src['last_original_arrival']
        buffer=io.StringIO(newline='');w=csv.DictWriter(buffer,fields,lineterminator='\n');w.writeheader();w.writerows(r for i,r in chosen)
        dst=ROOT/f'data/holdout_r3/saturn{src["workload"]}_supported80.csv';dst.parent.mkdir(exist_ok=True)
        data=buffer.getvalue().encode('utf8');assert not dst.exists() or dst.read_bytes()==data
        if not dst.exists():dst.write_bytes(data)
        assert list(csv.DictReader(dst.open(encoding='utf8',newline='')))==[r for i,r in chosen]
        derived.append(dict(source=src['source'],source_sha256=sha(p),source_rows=len(rows),eligible_rows=len(eligible),source_zero_based_indices=[i for i,r in chosen],rows=[dict(source_zero_based_row=i,fields=r) for i,r in chosen],output=dst.relative_to(ROOT).as_posix(),sha256=sha(dst),generator_sha256=sha(Path(__file__)),arrivals_preserved=True))
    dump(ROOT/'data/holdout_r3/provenance.json',derived)
    dump(DEV/'offline_validation_receipt.json',dict(status='PASS',replayed_states=len(results),history_sources_verified=len(sources),proportional_points=len(points),job_step_calls=0,holdout_workloads=2))
    print('R3_OFFLINE_VALIDATION_PASS',flush=True)
if __name__=='__main__':main()
