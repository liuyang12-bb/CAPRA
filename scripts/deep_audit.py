"""Independent cross-round replay of physical identities, restore clocks and locks.

Offline supplemental check; does not import capra, Sia, optimizer or simulator.
"""
from pathlib import Path
import ast,csv,gzip,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def recovery_costs():
    source=ROOT/'third_party/sia/sia-simulator/applications.py'
    tree=ast.parse(source.read_text(encoding='utf8'));costs={}
    for branch in ast.walk(tree):
        if not isinstance(branch,ast.If) or not isinstance(branch.test,ast.Compare):continue
        test=branch.test
        if len(test.comparators)!=1 or not isinstance(test.left,ast.Attribute) or test.left.attr!='name':continue
        name=test.comparators[0]
        if not isinstance(name,ast.Constant) or not isinstance(name.value,str):continue
        for statement in branch.body:
            if isinstance(statement,ast.Assign) and any(isinstance(t,ast.Attribute) and t.attr=='rescale_time' for t in statement.targets):
                costs[name.value]=float(ast.literal_eval(statement.value))
    assert {'cifar10','imagenet','bert','deepspeech2'}<=costs.keys()
    return costs


def gpu_key(a):return None if a is None else (a['node'],a['gpu_type'],a['gpus'])
def audit(directory):
    directory=Path(directory)
    for name,digest in json.loads((directory/'output_hashes.json').read_text()).items():assert sha(directory/name)==digest
    start=json.loads((directory/'start.json').read_text(encoding='utf8'))
    rows=list(csv.DictReader(Path(start['input']).open(encoding='utf8',newline='')))
    if start['max_jobs'] is not None:rows=rows[:start['max_jobs']]
    app={r['name']:r['application'] for r in rows};arrivals={r['name']:float(r['time']) for r in rows}
    node_map={n['id']:n for n in json.loads((ROOT/'configs/cluster.json').read_text())}
    cost=recovery_costs()
    last_alloc={};remaining={};complete=set();seen=set();last_end={};trained={k:0.0 for k in app};restored={k:0.0 for k in app}
    counts=dict(rounds=0,idle_rounds=0,physical_lock_checks=0,transition_checks=0,execution_checks=0,same_type_migrations=0,cross_type_migrations=0,quota_only_updates=0)
    with gzip.open(directory/'events.jsonl.gz','rt',encoding='utf8') as stream:
        for line in stream:
            r=json.loads(line);counts['rounds']+=1
            if not r['plan']:
                assert not any(at<=r['time'] and k not in complete for k,at in arrivals.items()),'EMPTY_ACTIVE_DECISION_EXCLUDED_FROM_OVERHEAD'
                counts['idle_rounds']+=1
            previous={k:a for k,a in last_alloc.items() if k not in complete}
            expected_locks={k:a for k,a in previous.items() if remaining.get(k,0)>1e-9}
            assert r['locks']==expected_locks,('MISSING_OR_CHANGED_LOCK',r['round'])
            counts['physical_lock_checks']+=len(expected_locks)
            new=r['allocations']
            assert set(new)==set(r['plan']),'INCOMPLETE_COMMIT'
            usage={k:[0.0,0.0,0.0] for k in node_map}
            for k,a in new.items():
                p=r['plan'][k];n=node_map[a['node']]
                assert a['gpu_type']==n['gpu_type']==p['gpu_type'] and p['nodes']==1 and a['gpus']==p['gpus']
                assert a['gpus'] in ([1,2,4] if n['gpus']==4 else [1,2,4,8])
                assert a['rho']>0 and a['cpu']>0 and a['ram']>0
                for j,key in enumerate(('gpus','cpu','ram')):usage[n['id']][j]+=a[key]
            for k,n in node_map.items():
                assert all(x<=n[key]+1e-7 for x,key in zip(usage[k],('gpus','cpu','ram'))),('CAPACITY_REPLAY',r['round'],k)
            assert usage==r['node_usage']
            if start['method'] in ('SIA-P','CAPRA-Fixed'):
                assert all(a['node']==r['plan'][k]['node'] for k,a in new.items()),'FIXED_PLACEMENT_CHANGED'
            original=r['gpu_stage'].get('original_sia_plan',{})
            assert set(original)==set(r['plan'])
            for k,p in r['plan'].items():
                assert p['gpu_type']==original[k]['gpu_type'] and p['gpus']==original[k]['gpus']
                if not r['gpu_stage']['repairs']:assert p['node']==original[k]['node']
            for k in expected_locks:assert new.get(k)==previous[k]
            events={e['job']:e for e in r['transitions']}
            assert len(events)==len(r['transitions'])
            for k in set(previous)|set(new):
                old=previous.get(k);a=new.get(k);e=events.get(k)
                if gpu_key(old)!=gpu_key(a):
                    assert e is not None
                    assert e['old']==old and e['new']==a
                    if a is None:
                        expected='suspend';expected_cost=0.0
                    else:
                        expected_cost=cost[app[k]]
                        expected=('resume' if k in seen else 'start') if old is None else ('migration' if old['node']!=a['node'] else 'reconfigure')
                    assert e['kind']==expected and e['cost']==expected_cost,(k,e,expected,expected_cost)
                    if a is not None:remaining[k]=expected_cost;seen.add(k)
                    if e['kind']=='migration':
                        assert old['node']!=a['node']
                        counts['same_type_migrations' if old['gpu_type']==a['gpu_type'] else 'cross_type_migrations']+=1
                elif old!=a:
                    assert e is not None and e['kind']=='aux_update' and e['cost']==0
                    counts['quota_only_updates']+=1
                else:assert e is None
                if e:counts['transition_checks']+=1
            for e in r['executions']:
                k=e['job'];assert k not in complete
                assert abs(e['start']-last_end.get(k,arrivals[k]))<1e-7,('CLOCK_GAP',k,e['start'],last_end.get(k,arrivals[k]))
                assert e['allocation']==new.get(k)
                before=remaining.get(k,0)
                expected_recovery=min(before,e['end']-e['start']) if k in new else 0.0
                assert abs(e['recovery']-expected_recovery)<1e-7,('RECOVERY_CLOCK',k,e,expected_recovery)
                if k in new:remaining[k]=max(0.0,before-expected_recovery)
                assert abs(e['rescale_remaining']-remaining.get(k,0))<1e-7,('RESCALE_REMAINING',k)
                if e['segments']:
                    assert abs(e['segments'][0]['start']-e['start']-e['recovery'])<1e-7,('TRAIN_BEFORE_RECOVERY',k)
                if e['completion_time'] is not None:complete.add(k)
                last_end[k]=e['end'];trained[k]+=e['training'];restored[k]+=e['recovery'];counts['execution_checks']+=1
            last_alloc=new
    term=json.loads((directory/'termination.json').read_text())
    assert len(complete)==term['completed'],'COMPLETION_COUNT_MISMATCH'
    return dict(status='PASS',output=str(directory),completed=len(complete),total=len(app),counts=counts,recovery_costs_from_frozen_sia_application=cost,scope='Cross-round node identity, transition cost, exact locks, absolute job clocks and recovery-before-training; supplements raw capacity/progress/rho/JCT audit.')


if __name__=='__main__':
    import sys
    if len(sys.argv)>1:
        result=audit(Path(sys.argv[1]));print(json.dumps(result,ensure_ascii=False,indent=2))
    else:
        results=json.loads((ROOT/'runs/main_v1/results.json').read_text(encoding='utf8'))
        audits=[]
        for r in results:
            if r.get('audit')=='PASS':audits.append(audit(ROOT/r['output']))
        target=ROOT/'runs/main_v1/deep_audit.json'
        target.write_text(json.dumps(audits,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print(json.dumps(dict(cells=len(audits),status='PASS',output=str(target)),ensure_ascii=False))
