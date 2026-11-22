"""Raw v2 replay: independent costs, mappings, candidate scores, execution and JCT.

No imports from placement/identity/costs/node_allocator or the Sia optimizer.
"""
from collections import Counter,defaultdict
from pathlib import Path
import ast,csv,gzip,json,hashlib
import numpy as np
from .audit import audit as common_audit
from .response import Responses
from .inputs import resolve_inputs

ROOT=Path(__file__).resolve().parents[2]
EPS=1e-9
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def key(a):return None if a is None else (a['node'],a['gpu_type'],a['gpus'])
def close(a,b):assert abs(a-b)<=1e-7,(a,b)
def app_costs():
    tree=ast.parse((ROOT/'third_party/sia/sia-simulator/applications.py').read_text(encoding='utf8'));out={}
    for v in ast.walk(tree):
        if isinstance(v,ast.If) and isinstance(v.test,ast.Compare) and isinstance(v.test.left,ast.Attribute) and v.test.left.attr=='name' and len(v.test.comparators)==1 and isinstance(v.test.comparators[0],ast.Constant):
            for s in v.body:
                if isinstance(s,ast.Assign) and any(isinstance(x,ast.Attribute) and x.attr=='rescale_time' for x in s.targets):out[v.test.comparators[0].value]=float(ast.literal_eval(s.value))
    return out

def prediction(k,a,current,locks,rem,apps,costs,seen):
    old=current.get(k)
    if k in locks:
        assert a==locks[k]
        return dict(kind='locked',new_cost=0.,existing_remaining=rem[k],delay=rem[k],gpu_change=False)
    if a is None:return dict(kind='suspend' if old else 'unchanged',new_cost=0.,existing_remaining=0.,delay=0.,gpu_change=old is not None)
    if key(a)==key(old):return dict(kind='unchanged' if a==old else 'aux_update',new_cost=0.,existing_remaining=0.,delay=0.,gpu_change=False)
    kind=('resume' if k in seen else 'start') if old is None else ('migration' if a['node']!=old['node'] else 'reconfigure')
    d=costs[apps[k]]
    return dict(kind=kind,new_cost=d,existing_remaining=0.,delay=d,gpu_change=True)

def score(alloc,current,locks,rem,apps,costs,seen):
    jobs={}
    for k,a in sorted(alloc.items()):
        t=prediction(k,a,current,locks,rem,apps,costs,seen)
        jobs[k]=dict(**t,rho=a['rho'],effective_window=max(0,180-t['delay']),contribution=a['rho']*max(0,1-t['delay']/180))
    return dict(phi=sum(x['contribution'] for x in jobs.values()),total_delay=sum(x['delay'] for x in jobs.values()),total_new_cost=sum(x['new_cost'] for x in jobs.values()),changes=sum(x['gpu_change'] for x in jobs.values()),jobs=jobs)

def stable(before,nodes,current,locks,rem,apps,costs,seen):
    a={k:dict(v) for k,v in before.items()};groups=defaultdict(list)
    for n in nodes.values():groups[(n['gpu_type'],n['gpus'],n['cpu'],n['ram'])].append(n['id'])
    for _,ids in sorted(groups.items()):
        ids=sorted(ids)
        if len(ids)!=2:continue
        swap=dict(zip(ids,ids[::-1]));b={k:dict(v,node=swap.get(v['node'],v['node'])) for k,v in a.items()}
        if not all(b.get(k)==v for k,v in locks.items()):continue
        da=score(a,current,locks,rem,apps,costs,seen)['total_delay'];db=score(b,current,locks,rem,apps,costs,seen)['total_delay']
        canonical=lambda x:tuple((k,v['node']) for k,v in sorted(x.items()))
        if db<da-EPS or (abs(db-da)<=EPS and canonical(b)<canonical(a)):a=b
    return a

def audit(directory):
    d=Path(directory);start=json.loads((d/'start.json').read_text(encoding='utf8'))
    assert start['version'].startswith('CAPRA_V2') and start['horizon']==180
    summary=common_audit(d)
    inputs=resolve_inputs(start)
    rows=list(csv.DictReader(inputs['workload'].open(encoding='utf8',newline='')))
    if start['max_jobs'] is not None:rows=rows[:start['max_jobs']]
    apps={r['name']:r['application'] for r in rows};arrivals={r['name']:float(r['time']) for r in rows}
    costs=app_costs();nodes={n['id']:n for n in json.loads(inputs['cluster'].read_text())}
    for app,values in start['costs'].items():assert all(v==costs[app] for v in values.values())
    response=Responses(inputs['responses'],start['neutral'])
    ca=response.data['cpu_axis'];ma=response.data['ram_axis']
    last={};rem={};seen=set();complete=set();last_end={};counts=Counter();selected=Counter();feasible=Counter();failed=Counter();gains=[]
    training=0.;weighted=0.;boosted=0.;app_train=Counter();new_cost_total=0.;node_only=0;pool_total=0;upgrade_total=0;node_cache=0
    def check_alloc(p,a,locks):
        assert set(p)==set(a),'CANDIDATE_INCOMPLETE'
        use={k:[0.,0.,0.] for k in nodes}
        for k,x in a.items():
            n=nodes[x['node']];g=x['gpus']
            assert x['gpu_type']==n['gpu_type']==p[k]['gpu_type'] and g==p[k]['gpus'] and p[k]['nodes']==1
            assert g in ([1,2,4] if n['gpus']==4 else [1,2,4,8])
            assert x['cpu']>=ca[0]*g-1e-7 and x['ram']>=ma[0]*g-1e-7,'BELOW_PROFILE_MINIMUM'
            rho=response.rho(apps[k],g,x['cpu'],x['ram']);close(rho,x['rho'])
            if k in locks:assert x==locks[k]
            else:assert rho+1e-7>=response.rho(apps[k],g,n['cpu']*g/n['gpus'],n['ram']*g/n['gpus'])
            for i,f in enumerate(('gpus','cpu','ram')):use[n['id']][i]+=x[f]
        for nid,u in use.items():assert all(v<=nodes[nid][f]+1e-7 for v,f in zip(u,('gpus','cpu','ram')))
        return use
    with gzip.open(d/'events.jsonl.gz','rt',encoding='utf8') as f:
        for line in f:
            r=json.loads(line);counts['rounds']+=1
            current={k:a for k,a in last.items() if k not in complete}
            assert current==r['current'] and set(r['started'])==seen
            locks={k:a for k,a in current.items() if rem.get(k,0)>EPS}
            assert locks==r['locks']
            assert r['lock_remaining']=={k:rem[k] for k in locks};counts['lock_checks']+=len(locks)
            p=r['plan'];raw=r['raw_sia_plan'];repaired=r['lock_repaired_gpu_plan']
            assert set(p)==set(raw)==set(repaired)
            for k in p:
                assert all(p[k][a]==repaired[k][a] for a in ('name','gpu_type','gpus','nodes','atomic_bsz','accum_steps'))
                assert p[k]['gpus']==raw[k]['gpus'] and p[k]['gpu_type']==raw[k]['gpu_type']
                if not r['gpu_stage']['repairs']:assert repaired[k]['node']==raw[k]['node']
            ref=r['reference'];check_alloc(repaired,ref['before'],locks)
            expected_ref=stable(ref['before'],nodes,current,locks,r['lock_remaining'],apps,costs,seen)
            assert expected_ref==ref['after'];assert all(p[k]['node']==expected_ref[k]['node'] for k in p)
            close(ref['mapping']['before_delay'],score(ref['before'],current,locks,r['lock_remaining'],apps,costs,seen)['total_delay'])
            close(ref['mapping']['after_delay'],score(expected_ref,current,locks,r['lock_remaining'],apps,costs,seen)['total_delay'])
            candidates=r['selection']['candidates'];assert len(candidates)<=3
            labels=[c['label'] for c in candidates]
            assert labels==(['P'] if start['method']=='SIA-P' else (['F'] if start['method']=='CAPRA-Fixed' else ['F','K','R']))
            valid=[]
            for c in candidates:
                label=c['label']
                if not c['feasible']:
                    assert label in ('K','R') and c['reason'];failed[label+':'+c['reason']]+=1;continue
                feasible[label]+=1;a=c['allocations'];check_alloc(p,a,locks)
                assert stable(c['mapping_before'],nodes,current,locks,r['lock_remaining'],apps,costs,seen)==a
                # Mapping changes only node identities and preserves all co-location groups.
                for k,x in a.items():assert all(x[field]==c['mapping_before'][k][field] for field in ('gpu_type','gpus','cpu','ram','rho'))
                for k in a:
                    for j in a:assert (a[k]['node']==a[j]['node'])==(c['mapping_before'][k]['node']==c['mapping_before'][j]['node'])
                s=score(a,current,locks,r['lock_remaining'],apps,costs,seen)
                for field in ('phi','total_delay','total_new_cost','changes'):close(s[field],c['score'][field])
                for k,t in s['jobs'].items():
                    for field in t:
                        if isinstance(t[field],(int,float)):close(t[field],c['score']['jobs'][k][field])
                        else:assert t[field]==c['score']['jobs'][k][field]
                if label in ('F','P'):assert all(x['node']==p[k]['node'] for k,x in a.items())
                for m in c['quota'].values():
                    assert 1<=m['initial_vectors']<=2 and m['upgrades']<=m['upgrade_bound']
                    assert m['upgrade_bound']==sum(v-1 for v in m['candidate_pairs'].values())
                valid.append((c,s))
            winner=valid[0]
            for candidate in valid[1:]:
                a,b=candidate[1],winner[1]
                if a['phi']>b['phi']+EPS or (abs(a['phi']-b['phi'])<=EPS and (a['total_delay']<b['total_delay']-EPS or (abs(a['total_delay']-b['total_delay'])<=EPS and a['changes']<b['changes']))):winner=candidate
            c,s=winner;assert r['selection']['selected']==c['label'];assert c['allocations']==r['allocations'];selected[c['label']]+=1
            if start['method']!='SIA-P':
                delta=s['phi']-valid[0][1]['phi'];assert delta>=-EPS;close(delta,r['selection']['relative_to_F']);gains.append(delta)
            usage=check_alloc(p,r['allocations'],locks);assert usage==r['node_usage']
            events={e['job']:e for e in r['transitions']};assert len(events)==len(r['transitions'])
            for k in set(current)|set(p):
                a=r['allocations'].get(k);old=current.get(k);t=prediction(k,a,current,locks,r['lock_remaining'],apps,costs,seen)
                if k in p:
                    for field in t:assert r['commit_predictions'][k][field]==t[field]
                    close(r['post_commit_remaining'][k],t['delay'])
                if t['kind'] not in ('unchanged','locked'):
                    e=events.pop(k);assert e['old']==old and e['new']==a and e['kind']==t['kind'];close(e['cost'],t['new_cost'])
                    counts[t['kind']]+=1;new_cost_total+=t['new_cost']
                    if t['kind']=='migration' and (old['gpu_type'],old['gpus'])==(a['gpu_type'],a['gpus']):node_only+=1
                if a is not None and t['gpu_change']:rem[k]=t['new_cost'];seen.add(k)
            assert not events
            for e in r['executions']:
                k=e['job'];assert k not in complete
                close(e['start'],last_end.get(k,arrivals[k]));assert e['allocation']==r['allocations'].get(k)
                recovery=min(rem.get(k,0),e['end']-e['start']) if e['allocation'] else 0.
                close(e['recovery'],recovery)
                if e['allocation']:rem[k]=max(0.,rem.get(k,0)-recovery)
                close(e['rescale_remaining'],rem.get(k,0))
                if e['segments']:close(e['segments'][0]['start'],e['start']+recovery)
                for seg in e['segments']:
                    training+=seg['seconds'];weighted+=seg['seconds']*seg['rho'];boosted+=seg['seconds']*(seg['rho']>1+EPS);app_train[apps[k]]+=seg['seconds']
                if e['completion_time'] is not None:complete.add(k)
                last_end[k]=e['end']
            astats=r['selection']['allocator'];pool_total+=astats['generated_pairs'];upgrade_total+=astats['upgrades'];node_cache+=astats['node_cache_hits']
            assert r['decision_seconds']+1e-6>=r['gpu_stage_seconds']+r['reference_seconds']+r['candidate_seconds']+r['commit_seconds']
            last=r['allocations']
    assert len(complete)==summary['completed']
    per=list(csv.DictReader((d/'per_job.csv').open(encoding='utf8',newline='')))
    jcts=[float(v['jct']) for v in per if v['jct']]
    window=summary['makespan'] if summary['makespan'] is not None else max(last_end.values(),default=0)-min(arrivals.values())
    avg={nid:{field:seconds[i]/window if window>0 else 0 for i,field in enumerate(('gpus','cpu','ram'))} for nid,seconds in summary['node_allocated_resource_seconds'].items()}
    occ={field:sum(v[field] for v in avg.values())/sum(n[field] for n in nodes.values()) for field in ('gpus','cpu','ram')}
    summary.update(version=start['version'],p50_jct=float(np.quantile(jcts,.5)) if len(complete)==len(apps) else None,
        mean_waiting=float(np.mean([float(x['waiting']) for x in per])),mean_training=float(np.mean([float(x['training']) for x in per])),mean_recovery=float(np.mean([float(x['recovery']) for x in per])),
        average_node_allocations=avg,allocated_resource_fraction=occ,occupancy_scope='Allocation time including recovery, not physical busy utilization',
        candidate_selected=dict(selected),candidate_feasible=dict(feasible),candidate_failures=dict(failed),relative_to_F=dict(median=float(np.median(gains)) if gains else None,p95=float(np.quantile(gains,.95)) if gains else None,max=max(gains,default=None)),
        pure_node_migrations=node_only,total_new_recovery_cost=new_cost_total,total_actual_recovery=sum(float(x['recovery']) for x in per),
        training_weighted_rho=weighted/training if training else None,boosted_training_fraction=boosted/training if training else None,
        application_training_share={k:v/training for k,v in app_train.items()} if training else {},quota_generated_pairs=pool_total,quota_upgrade_steps=upgrade_total,node_trial_cache_hits=node_cache,
        v2_raw_audit='PASS',independent_checks=dict(counts))
    (d/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (d/'v2_audit.json').write_text(json.dumps(dict(status='PASS',counts=dict(counts),selected=dict(selected),feasible=dict(feasible),failures=dict(failed),raw_rounds=counts['rounds']),indent=2)+'\n',encoding='utf8')
    (d/'audit_hashes.json').write_text(json.dumps({name:sha(d/name) for name in ('summary.json','per_job.csv','node_resources.csv','v2_audit.json')},indent=2)+'\n',encoding='utf8')
    return summary
