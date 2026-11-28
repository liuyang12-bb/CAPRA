"""Independent Direct audit: no direct placement, feasibility or allocator imports."""
from collections import Counter,defaultdict
from pathlib import Path
import csv,gzip,json,hashlib,time
import numpy as np
from .audit import audit as training_audit
from .audit_r4 import score,prediction,stable,app_costs,close
from .audit_ram_r2 import verify_trace
from .response import Responses
from .inputs import resolve_inputs

ROOT=Path(__file__).resolve().parents[2]
BASE='ffa953fb9cd12773992559512d85065bbd26b7b2'
VERSION='CAPRA_V2_DIRECT_R5';METHOD='CAPRA-Direct';EPS=1e-9;CAP_EPS=1e-7
FIELDS=('name','gpu_type','gpus','nodes','atomic_bsz','accum_steps')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def same_score(a,b):
    for f in ('phi','total_delay','total_new_cost','changes'):close(a[f],b[f])
    assert set(a['jobs'])==set(b['jobs'])
    for k,v in a['jobs'].items():
        for f,x in v.items():
            if isinstance(x,(int,float)):close(x,b['jobs'][k][f])
            else:assert x==b['jobs'][k][f]

def possible(contract,nodes,locks,response,layout,remaining):
    """Independent bounded 2D occupancy reachability; no optimized layout returned."""
    if set(layout)&set(remaining) or set(layout)|set(remaining)!=set(contract) or not set(locks)<=set(layout):return False,{}
    grouped=defaultdict(list);used={n:[0,0.,0.] for n in nodes}
    def legal(k,n):
        p=contract[k];g=p['gpus'];c=g*n['cpu']/n['gpus'];m=g*n['ram']/n['gpus']
        return p['gpu_type']==n['gpu_type'] and p['nodes']==1 and 0<g<=n['gpus'] and response.data['cpu_axis'][0]*g-1e-9<=c<=min(n['cpu'],response.data['cpu_axis'][-1]*g)+1e-9 and response.data['ram_axis'][0]*g-1e-9<=m<=min(n['ram'],response.data['ram_axis'][-1]*g)+1e-9
    for nid,n in nodes.items():grouped[n['gpu_type']].append(nid)
    for k,nid in layout.items():
        if k not in contract or nid not in nodes:return False,{}
        p=contract[k];n=nodes[nid];g=p['gpus']
        if p['gpu_type']!=n['gpu_type'] or g>n['gpus']:return False,{}
        if k in locks:
            a=locks[k]
            if (a['node'],a['gpu_type'],a['gpus'])!=(nid,p['gpu_type'],g):return False,{}
            c,m=a['cpu'],a['ram']
        else:
            if not legal(k,n):return False,{}
            c,m=g*n['cpu']/n['gpus'],g*n['ram']/n['gpus']
        for i,v in enumerate((g,c,m)):used[nid][i]+=v
    caps={}
    for nid,n in nodes.items():
        u=used[nid]
        if any(x>n[f]+CAP_EPS for x,f in zip(u,('gpus','cpu','ram'))):return False,{}
        fits=[g for g in range(n['gpus']+1) if u[0]+g<=n['gpus'] and u[1]+g*n['cpu']/n['gpus']<=n['cpu']+CAP_EPS and u[2]+g*n['ram']/n['gpus']<=n['ram']+CAP_EPS]
        if not fits:return False,{}
        caps[nid]=max(fits)
    for typ,ids in grouped.items():
        ids=sorted(ids);assert 1<=len(ids)<=2,'UNSUPPORTED_SCOPE'
        states={(0,0)}
        for k in sorted(remaining):
            if contract[k]['gpu_type']!=typ:continue
            g=contract[k]['gpus'];new=set()
            for a,b in states:
                if legal(k,nodes[ids[0]]) and a+g<=caps[ids[0]]:new.add((a+g,b))
                if len(ids)==2 and legal(k,nodes[ids[1]]) and b+g<=caps[ids[1]]:new.add((a,b+g))
            states=new
            if not states:return False,caps
    return True,caps

def node_better(a,b):
    if abs(a['delta']-b['delta'])>EPS:return a['delta']>b['delta']
    if abs(a['inserted_new_cost']-b['inserted_new_cost'])>EPS:return a['inserted_new_cost']<b['inserted_new_cost']
    return (not a['keeps_current_node'],a['node'])<(not b['keeps_current_node'],b['node'])
def complete_better(a,b):
    if abs(a['phi']-b['phi'])>EPS:return a['phi']>b['phi']
    if abs(a['total_delay']-b['total_delay'])>EPS:return a['total_delay']<b['total_delay']
    return a['changes']<b['changes']

def audit_selection(witness,s,nodes,apps,response,current,locks,remaining,costs,started):
    costs={k:(next(iter(v.values())) if isinstance(v,dict) else v) for k,v in costs.items()}
    contract={k:{f:p[f] for f in FIELDS} for k,p in sorted(witness.items())}
    assert contract==s['contract'] and digest(contract)==s['contract_fingerprint']
    assert [x['where'] for x in s['contract_checks'][:2]]==['BEFORE_F_D','AFTER_F_D']
    assert all(x['fingerprint']==digest(contract) for x in s['contract_checks'])
    assert s['identity_scope']=='F_ONLY_REFERENCE; D_PHYSICAL_IDS_UNCHANGED'
    assert s['horizon']==180 and s['D_status'] in ('COMPLETE','D_BUDGET','D_NOT_STARTED_BUDGET')
    def sc(a):return score(a,current,locks,remaining,apps,costs,set(started))
    def alloc(a,ids):
        assert set(a)==set(ids);use={n:[0.,0.,0.] for n in nodes}
        for k,x in a.items():
            n=nodes[x['node']];p=contract[k];g=p['gpus'];ca=response.data['cpu_axis'];ma=response.data['ram_axis']
            assert p['nodes']==1 and (x['gpu_type'],x['gpus'])==(p['gpu_type'],g) and x['gpu_type']==n['gpu_type']
            assert ca[0]*g-1e-9<=x['cpu']<=min(n['cpu'],ca[-1]*g)+1e-9
            assert ma[0]*g-1e-9<=x['ram']<=min(n['ram'],ma[-1]*g)+1e-9
            close(x['rho'],response.rho(apps[k],g,x['cpu'],x['ram']))
            if k in locks:assert x==locks[k]
            else:assert x['rho']>=response.rho(apps[k],g,g*n['cpu']/n['gpus'],g*n['ram']/n['gpus'])-EPS
            for i,f in enumerate(('gpus','cpu','ram')):use[x['node']][i]+=x[f]
        for nid,u in use.items():assert all(x<=nodes[nid][f]+CAP_EPS for x,f in zip(u,('gpus','cpu','ram')))
    traces=s['allocation_traces'];ram=s['allocator']['ram_traces']
    assert len(traces)==len(ram)==s['counts']['cold_solves']
    for i,t in enumerate(traces):
        assert t['id']==i and t['jobs']==sorted(t['allocations']) and t['ram_trace_id']==i
        assert all(x['node']==t['node'] for x in t['allocations'].values())
        alloc(t['allocations'],t['jobs']);same_score(sc(t['allocations']),t['score'])
        assert ram[i]['trace_id']==i and ram[i]['final']==t['allocations']
        verify_trace(ram[i],nodes[t['node']],apps,response,locks)
    requests=s['solve_requests'];keys={};hits=0
    for r in requests:
        k=(r['node'],tuple(r['jobs']));assert r['jobs']==sorted(r['jobs'])
        warm=k in keys;assert r['cache_hit']==warm;hits+=warm
        if not warm:keys[k]=len(keys)
        assert r['trace_id']==keys[k];t=traces[r['trace_id']];assert (t['node'],t['jobs'])==(r['node'],r['jobs'])
    M=len(contract)-len(locks);N=len(nodes);counts=s['counts'];ast=s['allocator']
    assert len(requests)==counts['solve_requests']==ast['ram_requests']<=2*M+2*N
    assert hits==counts['cache_hits']==ast['ram_cache_hits'] and len(keys)==ast['node_calls']
    assert sum(r['phase']=='D_AFTER' for r in requests)<=2*M
    assert counts['solve_request_bound']==2*M+2*N and counts['D_after_request_bound']==2*M
    assert counts['response_queries']==counts['response_hits']+counts['response_misses'] and counts['response_misses']>=0
    ref=s['f_reference'];assert ref['input_witness']==witness
    prop={}
    for k,p in witness.items():
        n=nodes[p['node']];g=p['gpus'];c=n['cpu']*g/n['gpus'];m=n['ram']*g/n['gpus']
        prop[k]=locks[k] if k in locks else dict(node=n['id'],gpu_type=p['gpu_type'],gpus=g,cpu=c,ram=m,rho=response.rho(apps[k],g,c,m))
    assert ref['details']['before']==prop
    expected=stable(prop,nodes,current,locks,remaining,apps,costs,set(started))
    assert expected==ref['details']['after']
    assert set(ref['output_plan'])==set(contract)
    for k,p in ref['output_plan'].items():
        assert all(p[f]==contract[k][f] for f in FIELDS) and p['node']==expected[k]['node']
    candidates=s['candidates'];assert [c['label'] for c in candidates]==['F','D'];f,d=candidates;assert f['feasible']
    def combined(refs):
        a={}
        for nid,tid in refs.items():
            assert traces[tid]['node']==nid
            assert not set(a)&set(traces[tid]['allocations']);a.update(traces[tid]['allocations'])
        return a
    assert combined(f['trace_ids'])==f['allocations'];alloc(f['allocations'],contract);same_score(sc(f['allocations']),f['score'])
    assert all(f['allocations'][k]['node']==ref['output_plan'][k]['node'] for k in contract)
    close(ref['details']['mapping']['before_delay'],sc(prop)['total_delay']);close(ref['details']['mapping']['after_delay'],sc(expected)['total_delay'])
    prefix={k:a['node'] for k,a in sorted(locks.items())};refs={};dp=0;preferred_count=0
    def check(log,layout,left):
        nonlocal dp
        dp+=1;value,capacities=possible(contract,nodes,locks,response,layout,left)
        assert value==log['feasible'],'INDEPENDENT_CAN_FINISH'
        assert bool(log['reason'])
        if 'reservations' in log:
            for nid,r in log['reservations'].items():assert r['effective_gpus']==capacities[nid]
        return value
    if s['initial_check'] is not None:
        assert check(s['initial_check'],prefix,set(contract)-set(locks))
    init_requests=[r for r in requests if r['phase']=='LOCK_INITIAL']
    for r in init_requests:
        assert r['jobs']==sorted(k for k,n in prefix.items() if n==r['node']);refs[r['node']]=r['trace_id']
    assert [r['node'] for r in init_requests]==sorted(nodes)[:len(init_requests)]
    initial_todo=sorted(set(contract)-set(locks));ordering=[]
    for index,row in enumerate(s['ordering']):
        k=initial_todo[index];assert row['job']==k
        matching=sorted(n for n in nodes if nodes[n]['gpu_type']==contract[k]['gpu_type']);legal=[];pressures=[]
        assert [c['node'] for c in row['candidates']]==matching[:len(row['candidates'])]
        for c in row['candidates']:
            trial=dict(prefix);trial[k]=c['node'];ok=check(c['can_finish'],trial,set(initial_todo)-{k})
            if ok and 'pressure' in c:
                # Frozen-table joint preferred point; no allocator/placement invocation.
                from types import SimpleNamespace
                n=nodes[c['node']];cpu,mem=response.preferred(apps[k],contract[k]['gpus'],SimpleNamespace(**n));preferred_count+=1
                close(cpu,c['preferred_cpu']);close(mem,c['preferred_ram'])
                p=max(0,cpu/n['cpu']-contract[k]['gpus']/n['gpus'],mem/n['ram']-contract[k]['gpus']/n['gpus'])
                close(p,c['pressure']);legal.append(c['node']);pressures.append(p)
            elif ok:assert not row['complete'] and s['D_status']=='D_BUDGET'
        assert row['legal_nodes']==legal
        if row['complete']:
            assert len(row['candidates'])==len(matching) and pressures
            close(row['pressure'],max(pressures));ordering.append((len(legal),-contract[k]['gpus'],-round(max(pressures),12),k))
        else:assert index==len(s['ordering'])-1 and s['order'] is None
    if s['order'] is not None:
        assert len(ordering)==len(initial_todo) and s['order']==[x[-1] for x in sorted(ordering)]
        assert set(refs)==set(nodes)
    for index,step in enumerate(s['steps']):
        assert s['order'] is not None and step['job']==s['order'][index] and step['index']==index
        k=step['job'];matching=sorted(n for n in nodes if nodes[n]['gpu_type']==contract[k]['gpu_type']);options=[]
        assert [c['node'] for c in step['candidates']]==matching[:len(step['candidates'])]
        for c in step['candidates']:
            trial=dict(prefix);trial[k]=c['node'];ok=check(c['can_finish'],trial,s['order'][index+1:])
            if not ok:assert 'after_trace_id' not in c;continue
            if 'after_trace_id' not in c:
                assert not step['complete'] and s['D_status']=='D_BUDGET';continue
            before=traces[c['before_trace_id']];after=traces[c['after_trace_id']]
            assert c['before_trace_id']==refs[c['node']]
            assert before['jobs']==sorted(j for j,n in prefix.items() if n==c['node'])
            assert after['node']==c['node'] and after['jobs']==sorted(before['jobs']+[k])
            close(c['delta'],after['score']['phi']-before['score']['phi'])
            close(c['inserted_new_cost'],after['score']['jobs'][k]['new_cost'])
            assert c['keeps_current_node']==(k in current and current[k]['node']==c['node']);options.append(c)
        if step['complete']:
            assert len(step['candidates'])==len(matching) and options
            winner=options[0]
            for c in options[1:]:
                if node_better(c,winner):winner=c
            assert step['chosen_node']==winner['node'],'WRONG_NODE_DELTA_CHOICE'
            prefix[k]=winner['node'];refs[winner['node']]=winner['after_trace_id']
        else:
            assert step['chosen_node'] is None and index==len(s['steps'])-1 and s['D_status']=='D_BUDGET'
    assert prefix==s['prefix_layout'] and refs==s['prefix_trace_ids']
    assert counts['dp_checks']==dp and counts['preferred_queries']==preferred_count
    if s['D_status']=='COMPLETE':
        assert d['feasible'] and len(s['steps'])==M and set(prefix)==set(contract)
        assert combined(refs)==d['allocations'] and d['trace_ids']==refs
        assert {k:a['node'] for k,a in d['allocations'].items()}==prefix,'POST_D_IDENTITY'
        alloc(d['allocations'],contract);same_score(sc(d['allocations']),d['score'])
        close(d['score']['phi'],sum(traces[i]['score']['phi'] for i in refs.values()))
    else:
        assert not d['feasible'] and d['reason']==s['D_status'] and 'allocations' not in d and 'score' not in d
        assert s['selected']=='F' and s['candidate_seconds']>=s['budget_seconds']
        if s['D_status']=='D_NOT_STARTED_BUDGET':assert not s['steps'] and s['initial_check'] is None
    winner=d if d['feasible'] and complete_better(d['score'],f['score']) else f
    assert s['selected']==winner['label'];close(s['phi'],winner['score']['phi']);close(s['relative_to_F'],winner['score']['phi']-f['score']['phi'])
    assert s['relative_to_F']>=-EPS
    assert all(v>=0 for v in s['timing'].values());assert s['timing']['f_reference']+s['timing']['f_quota']+s['timing']['D']<=s['candidate_seconds']+1e-6
    close(s['budget_overrun_seconds'],max(0,s['candidate_seconds']-s['budget_seconds']))
    return winner['allocations']

def audit(directory):
    began=time.perf_counter();d=Path(directory).resolve();assert d.is_relative_to(ROOT/'runs/direct_r5'),'REFUSE_HISTORY_WRITE'
    start=json.loads((d/'start.json').read_text(encoding='utf8'))
    assert (start['version'],start['base_commit'],start['method'],start['allocator_mode'],start['interval'],start['horizon'],start['seed'])==(VERSION,BASE,METHOD,'ram_slack_v1',60,180,0)
    assert start['numeric_environment']==dict(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONHASHSEED='0')
    assert (start['python'],start['numpy'],start['scipy'],start['cvxpy'])==('3.10.10','1.26.4','1.13.1','1.6.5')
    for p,h in start['source_files_sha256'].items():assert sha(ROOT/p)==h,('SOURCE_CHANGED',p)
    assert str(ROOT.resolve())==start['import_audit']['ROOT']
    for path in start['import_audit']['module_files'].values():
        p=Path(path)
        if p.drive.lower()=='d:':assert p.resolve().is_relative_to(ROOT.resolve()),('FOREIGN_IMPORT',path)
    assert Path(start['import_audit']['prefix']).resolve()==ROOT/'.venv'
    summary=training_audit(d);inputs=resolve_inputs(start);response=Responses(inputs['responses']);nodes={n['id']:n for n in json.loads(inputs['cluster'].read_text(encoding='utf8'))}
    rows=list(csv.DictReader(inputs['workload'].open(encoding='utf8',newline='')))[:start['max_jobs']]
    apps={r['name']:r['application'] for r in rows};arrivals={r['name']:float(r['time']) for r in rows};costs=app_costs()
    for a,v in start['costs'].items():assert all(x==costs[a] for x in v.values())
    current={};rem={};seen=set();complete=set();last_end={};counts=Counter();nonempty=Counter();times=[];components=defaultdict(list)
    with gzip.open(d/'events.jsonl.gz','rt',encoding='utf8') as f:
        for line in f:
            r=json.loads(line);assert r['version']==VERSION and r['method']==METHOD
            assert r['gpu_stage_calls']==r['commit_calls']==1 and r['provenance_fingerprint']==start['provenance_fingerprint']
            assert r['current']=={k:a for k,a in current.items() if k not in complete} and set(r['started'])==seen;current=r['current']
            locks={k:a for k,a in current.items() if rem.get(k,0)>EPS};assert locks==r['locks'] and r['lock_remaining']=={k:rem[k] for k in locks}
            witness=r['lock_repaired_gpu_plan'];assert witness==r['plan'] and set(witness)==set(r['raw_sia_plan'])
            for k,p in witness.items():assert all(p[f]==r['raw_sia_plan'][k][f] for f in ('gpu_type','gpus'))
            a=audit_selection(witness,r['selection'],nodes,apps,response,current,locks,r['lock_remaining'],start['costs'],seen)
            assert r['selection']['contract_checks'][-1]['where']=='BEFORE_COMMIT';assert a==r['allocations']
            counts['rounds']+=1;counts['D_'+r['selection']['D_status']]+=1;counts['selected_'+r['selection']['selected']]+=1
            if witness:
                nonempty['rounds']+=1;nonempty['D_'+r['selection']['D_status']]+=1;nonempty['selected_'+r['selection']['selected']]+=1;times.append(r['decision_seconds'])
                for k,v in r['selection']['timing'].items():components[k].append(v)
                for k in ('gpu_stage_seconds','commit_seconds'):components[k].append(r[k])
            events={x['job']:x for x in r['transitions']};assert len(events)==len(r['transitions'])
            for k in set(current)|set(witness):
                pred=prediction(k,a.get(k),current,locks,r['lock_remaining'],apps,costs,seen)
                if k in witness:
                    assert pred==r['commit_predictions'][k];close(r['post_commit_remaining'][k],pred['delay'])
                if pred['kind'] not in ('unchanged','locked'):
                    e=events.pop(k);assert (e['old'],e['new'],e['kind'])==(current.get(k),a.get(k),pred['kind']);close(e['cost'],pred['new_cost']);assert e['prediction']==pred
                if k in a and pred['gpu_change']:rem[k]=pred['new_cost'];seen.add(k)
            assert not events
            for e in r['executions']:
                k=e['job'];assert k not in complete;close(e['start'],last_end.get(k,arrivals[k]));assert e['allocation']==a.get(k)
                rec=min(rem.get(k,0),e['end']-e['start']) if e['allocation'] else 0.;close(rec,e['recovery'])
                if e['allocation']:rem[k]=max(0.,rem.get(k,0)-rec)
                close(rem.get(k,0),e['rescale_remaining'])
                if e['segments']:close(e['segments'][0]['start'],e['start']+rec)
                if e['completion_time'] is not None:complete.add(k)
                last_end[k]=e['end']
            assert r['gpu_stage_seconds']+r['selection']['candidate_seconds']+r['commit_seconds']<=r['decision_seconds']+1e-6
            current=a
    def dist(v):return dict(n=len(v),median=float(np.median(v)),p95=float(np.quantile(v,.95)),p99=float(np.quantile(v,.99)),max=max(v)) if v else None
    per=list(csv.DictReader((d/'per_job.csv').open(encoding='utf8',newline='')));all_done=len(complete)==len(apps)
    assert len(complete)==summary['completed'] and summary['rounds']==counts['rounds']
    if not all_done:assert all(summary[k] is None for k in ('mean_jct','p95_jct','p99_jct','makespan'))
    summary.update(version=VERSION,base_commit=BASE,submitted=len(apps),arrived=sum(v<json.loads((d/'termination.json').read_text())['simulated_seconds'] for v in arrivals.values()),unfinished=len(apps)-len(complete),direct_raw_audit='PASS',algorithm_counts_all_rounds=dict(counts),algorithm_counts_nonempty_rounds=dict(nonempty),decision_distribution=dist(times),component_times={k:dist(v) for k,v in components.items()},timing_scope='F reference/F quota/D are sequential; completion/allocator/scoring are nested, do not sum. Wall decision not charged to JCT.',mean_waiting=float(np.mean([float(x['waiting']) for x in per])),mean_training=float(np.mean([float(x['training']) for x in per])),mean_recovery=float(np.mean([float(x['recovery']) for x in per])),audit_seconds=time.perf_counter()-began,formal_performance_experiment='NOT_RUN')
    (d/'summary.json').write_bytes((json.dumps(summary,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    (d/'direct_audit.json').write_bytes((json.dumps(dict(status='PASS',all_rounds=dict(counts),nonempty_rounds=dict(nonempty),independent_can_finish='two-dimensional bounded occupancy DP',no_placement_or_allocator_invocation=True,training_rho_once_checks=summary['segment_checks']),ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    (d/'audit_hashes.json').write_bytes((json.dumps({n:sha(d/n) for n in ('summary.json','per_job.csv','node_resources.csv','direct_audit.json')},indent=2)+'\n').encode('utf8'))
    return summary

if __name__=='__main__':
    import sys
    print(json.dumps(audit(sys.argv[1]),ensure_ascii=False))
