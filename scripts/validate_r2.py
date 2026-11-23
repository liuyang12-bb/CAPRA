"""Fixed bounded state replay and all R1 RAM certificates; no GPU simulator/step."""
from collections import defaultdict
from pathlib import Path
import csv,gzip,json,math,time
from r2_utils import *
from capra.contracts import Node,Allocation,JobGpuPlan,serialized
from capra.response_v2 import V2Responses
from capra.response import Responses
from capra.placement_r2 import PlacementR2
from capra.ram_slack import repair
from capra.audit_ram_r2 import verify_trace
SCENARIOS=('w2_dense_original','w6_dense_original','w2_dense_cm')
OLD=ROOT/'runs/scenarios_r1/CAPRA_V2_SCENARIOS_R1'
def events(d):
    with gzip.open(d/'events.jsonl.gz','rt',encoding='utf8') as f:return [json.loads(x) for x in f]
def semantic(c):
    if isinstance(c,dict):return {k:semantic(v) for k,v in c.items() if k not in ('generation_seconds','ram_repair_seconds')}
    if isinstance(c,list):return [semantic(x) for x in c]
    return c
def equal(a,b,path=''):
    if isinstance(a,dict):assert set(a)==set(b),(path,set(a)^set(b));[equal(a[k],b[k],path+'/'+k) for k in a]
    elif isinstance(a,list):assert len(a)==len(b),path;[equal(x,y,path) for x,y in zip(a,b)]
    elif isinstance(a,(int,float)) and not isinstance(a,bool):assert abs(a-b)<=1e-7,(path,a,b)
    else:assert a==b,(path,a,b)
def replay():
    began=time.perf_counter();selection=[];results=[];fkmatches=0
    for scenario in SCENARIOS:
        for method in ('SIA-P','CAPRA-Fixed','CAPRA'):
            d=OLD/scenario/method;start=load(d/'start.json');raw=events(d);active=[r for r in raw if r['plan']]
            chosen={r['round'] for r in active[:2]+active[-2:]};reasons={str(r['round']):['first2_or_last2_active'] for r in active[:2]+active[-2:]}
            for label,predicate in [('first_K_selected',lambda r:r['selection']['selected']=='K'),('first_R_selected',lambda r:r['selection']['selected']=='R'),('first_lock',lambda r:bool(r['locks'])),('first_K_infeasible',lambda r:any(c['label']=='K' and not c['feasible'] for c in r['selection']['candidates']))]:
                found=next((r for r in active if predicate(r)),None)
                selection.append(dict(scenario=scenario,method=method,rule=label,round=None if found is None else found['round']))
                if found:chosen.add(found['round']);reasons.setdefault(str(found['round']),[]).append(label)
            rows=list(csv.DictReader((ROOT/start['inputs']['workload']['relative']).open(encoding='utf8')));apps={r['name']:r['application'] for r in rows}
            nodes=[Node(**n) for n in load(ROOT/start['inputs']['cluster']['relative'])]
            for r in raw:
                if r['round'] not in chosen:continue
                check_budget();response=V2Responses(ROOT/start['inputs']['responses']['relative'])
                args=({k:JobGpuPlan(**v) for k,v in r['plan'].items()},nodes,apps,response,{k:Allocation(**v) for k,v in r['current'].items()},{k:Allocation(**v) for k,v in r['locks'].items()},r['lock_remaining'],start['costs'],set(r['started']))
                mode='none' if method=='SIA-P' else 'legacy';a,s=PlacementR2(*args,method=method,allocator_mode=mode).select()
                equal(semantic(s['candidates']),semantic(r['selection']['candidates']));equal(serialized(a),r['allocations']);assert s['selected']==r['selection']['selected']
                equal(s['phi'],r['selection']['phi']);equal(s['relative_to_F'],r['selection']['relative_to_F'])
                if method=='CAPRA':
                    a,fk=PlacementR2(*args,method='CAPRA-FK',allocator_mode='legacy').select()
                    equal(semantic(fk['candidates']),semantic(r['selection']['candidates'][:2]));assert fk['r_calls']==0;fkmatches+=1
                results.append(dict(scenario=scenario,method=method,round=r['round'],reasons=reasons[str(r['round'])],status='PASS'))
    dump(DEV/'state_replay_selection.json',selection);dump(DEV/'state_replay_results.json',results)
    record('offline_legacy_state_replay',wall_seconds=time.perf_counter()-began,states=len(results),FK_correspondences=fkmatches,job_step_calls=0,status='PASS')
    return len(results)
def certificates():
    began=time.perf_counter();groups=defaultdict(list);source=[];alltraces=[];total=0
    for method in ('CAPRA-Fixed','CAPRA'):
        d=OLD/'w2_dense_cm'/method;s=load(d/'start.json');nodes={n['id']:Node(**n) for n in load(ROOT/s['inputs']['cluster']['relative'])}
        rows=list(csv.DictReader((ROOT/s['inputs']['workload']['relative']).open(encoding='utf8')));apps={r['name']:r['application'] for r in rows}
        cert=[c for c in load(d/'analysis_r1/slack_certificates.json') if c['ram_candidate_gap']]
        byround=defaultdict(list)
        for c in cert:byround[c['round']].append(c)
        original_response=Responses(ROOT/s['inputs']['responses']['relative']);response=V2Responses(ROOT/s['inputs']['responses']['relative'])
        for r in events(d):
            if r['round'] not in byround:continue
            check_budget();by_node=defaultdict(list)
            for c in byround[r['round']]:
                a=r['allocations'][c['job']];n=nodes[a['node']];u=r['node_usage'][a['node']]
                assert c['job'] not in r['locks'] and abs(c['free_ram']-(n.ram-u[2]))<1e-6
                assert u[2]-a['ram']+c['proposed_ram']<=n.ram+1e-7
                rho=original_response.rho(apps[c['job']],a['gpus'],a['cpu'],c['proposed_ram'])
                assert abs(rho-c['rho_ram_only'])<1e-7 and rho>a['rho']+1e-9
                total+=1;by_node[a['node']].append(c)
            for nid,cs in sorted(by_node.items()):
                initial={k:Allocation(**a) for k,a in r['allocations'].items() if a['node']==nid};locks={k:Allocation(**v) for k,v in r['locks'].items() if v['node']==nid}
                out,trace=repair(nodes[nid],initial,apps,response,locks)
                verify_trace(trace,vars(nodes[nid]),apps,original_response,{k:vars(v) for k,v in locks.items()})
                alltraces.append(dict(source_method=method,round=r['round'],source_certificates=len(cs),**trace))
        source.append(dict(method=method,path=(d/'events.jsonl.gz').relative_to(ROOT).as_posix(),sha256=sha(d/'events.jsonl.gz'),certificate_count=len(cert)))
    assert total==288
    dump(DEV/'ram_certificate_group_replays.json',alltraces)
    receipt=dict(status='PASS',old_certificate_count=total,group_count=len(alltraces),accepted_updates=sum(t['ram_steps'] for t in alltraces),terminal_positive_opportunities=0,sources=source,
        warning='Groups are complete actual node states; shared slack updated sequentially, independent maxima are not summed or converted to JCT')
    dump(DEV/'ram_certificate_replay_receipt.json',receipt);record('offline_all_ram_certificates',wall_seconds=time.perf_counter()-began,**receipt)
    return receipt
def main():
    states=replay();cs=certificates();dump(DEV/'offline_validation_receipt.json',dict(status='PASS',legacy_states=states,ram_certificates=288,grouped_nodes=cs['group_count']))
    print('R2_OFFLINE_VALIDATION_PASS',flush=True)
if __name__=='__main__':main()
