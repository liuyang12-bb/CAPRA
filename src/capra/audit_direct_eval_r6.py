"""Portable pure raw-log audit. No placement, GPU optimizer or Job imports/calls."""
from pathlib import Path
from collections import Counter,defaultdict
import csv,gzip,json,time,math
import numpy as np
from .protocol_direct_eval_r6 import ROOT,RUN,BASE,R4,VERSION,NUMERIC,EPS,CAP_EPS,load,dump,sha,digest,input_rows
from .response import Responses
from .audit_r4 import score,prediction,stable,app_costs,close
from .audit_direct_r5 import audit_selection,same_score
from .audit_ram_r2 import verify_trace
from .audit_smart_r4 import check_start as smart_start,check_round as smart_round

class AuditResponses(Responses):
    """Exact-key mathematical memoization only; no production model cache changes."""
    def __init__(self,p):super().__init__(p);self.exact={}
    def rho(self,app,g,c,m):
        k=(app,g,c,m)
        if k not in self.exact:self.exact[k]=super().rho(app,g,c,m)
        return self.exact[k]

def check_alloc(p,a,nodes,apps,response,locks):
    assert set(p)==set(a),'INCOMPLETE_ALLOCATION';use={n:[0.,0.,0.] for n in nodes}
    for k,x in a.items():
        n=nodes[x['node']];g=p[k]['gpus'];ca=response.data['cpu_axis'];ma=response.data['ram_axis']
        assert p[k]['nodes']==1 and x['gpu_type']==p[k]['gpu_type']==n['gpu_type'] and x['gpus']==g
        assert ca[0]*g-1e-9<=x['cpu']<=min(n['cpu'],ca[-1]*g)+1e-9
        assert ma[0]*g-1e-9<=x['ram']<=min(n['ram'],ma[-1]*g)+1e-9
        close(x['rho'],response.rho(apps[k],g,x['cpu'],x['ram']))
        if k in locks:assert x==locks[k]
        else:assert x['rho']>=response.rho(apps[k],g,n['cpu']*g/n['gpus'],n['ram']*g/n['gpus'])-1e-7
        for i,f in enumerate(('gpus','cpu','ram')):use[x['node']][i]+=x[f]
    for nid,u in use.items():assert all(x<=nodes[nid][f]+CAP_EPS for x,f in zip(u,('gpus','cpu','ram')))
    return use

def reference_check(witness,ref,nodes,apps,response,current,locks,rem,costs,seen):
    prop={}
    for k,p in witness.items():
        n=nodes[p['node']];g=p['gpus'];c=n['cpu']*g/n['gpus'];m=n['ram']*g/n['gpus']
        prop[k]=locks[k] if k in locks else dict(node=n['id'],gpu_type=p['gpu_type'],gpus=g,cpu=c,ram=m,rho=response.rho(apps[k],g,c,m))
    assert prop==ref['before'];check_alloc(witness,prop,nodes,apps,response,locks)
    expected=stable(prop,nodes,current,locks,rem,apps,costs,seen);assert expected==ref['after']
    close(ref['mapping']['before_delay'],score(prop,current,locks,rem,apps,costs,seen)['total_delay'])
    close(ref['mapping']['after_delay'],score(expected,current,locks,rem,apps,costs,seen)['total_delay'])
    return expected

def check_f_only(r,nodes,apps,response,costs):
    s=r['selection'];p=r['plan'];cur=r['current'];locks=r['locks'];rem=r['lock_remaining'];seen=set(r['started'])
    fields=('name','gpu_type','gpus','nodes','atomic_bsz','accum_steps');contract={k:{f:x[f] for f in fields} for k,x in sorted(p.items())}
    assert s['contract']==contract and s['contract_fingerprint']==digest(contract)
    assert [x['where'] for x in s['contract_checks']]==['BEFORE_F_ONLY','AFTER_F_ONLY','BEFORE_COMMIT']
    assert all(x['fingerprint']==digest(contract) for x in s['contract_checks'])
    assert s['candidate_labels']==['F'] and s['selected']=='F' and s['D_status']=='NOT_APPLICABLE_F_ONLY'
    assert s['initial_check'] is None and not s['ordering'] and s['order'] is None and not s['steps'] and not s['prefix_trace_ids']
    for k in ('dp_checks','preferred_queries','budget_checks','D_after_calls','D_construct_calls'):assert s['counts'][k]==0
    assert s['timing']['D']==s['timing']['completion_checks_nested']==0 and s['budget_overrun_seconds']==0
    assert len(s['candidates'])==1;f=s['candidates'][0];assert f['label']=='F' and f['feasible']
    ref=s['f_reference'];assert ref['input_witness']==p
    expected=reference_check(p,ref['details'],nodes,apps,response,cur,locks,rem,costs,seen)
    for k,q in ref['output_plan'].items():assert all(q[a]==contract[k][a] for a in fields) and q['node']==expected[k]['node']
    traces=s['allocation_traces'];ram=s['allocator']['ram_traces'];assert len(traces)==len(ram)==s['counts']['cold_solves']
    for i,t in enumerate(traces):
        assert t['id']==i and t['ram_trace_id']==i and t['jobs']==sorted(t['allocations'])
        assert all(x['node']==t['node'] for x in t['allocations'].values())
        check_alloc({k:p[k] for k in t['jobs']},t['allocations'],nodes,apps,response,{k:v for k,v in locks.items() if k in t['jobs']})
        same_score(score(t['allocations'],cur,locks,rem,apps,costs,seen),t['score'])
        assert ram[i]['final']==t['allocations'];verify_trace(ram[i],nodes[t['node']],apps,response,locks)
    combined={};refs=f['trace_ids']
    for nid,tid in refs.items():
        assert traces[tid]['node']==nid and not set(combined)&set(traces[tid]['allocations']);combined.update(traces[tid]['allocations'])
    assert combined==f['allocations']==r['allocations']
    assert all(f['allocations'][k]['node']==ref['output_plan'][k]['node'] for k in p)
    requests=s['solve_requests'];assert all(x['phase']=='F' for x in requests)
    assert len(requests)==len(traces)==s['allocator']['ram_requests']==s['counts']['solve_requests']<=len(nodes)
    for x in requests:
        assert not x['cache_hit'];t=traces[x['trace_id']];assert (x['node'],x['jobs'])==(t['node'],t['jobs'])
    assert s['counts']['cache_hits']==s['allocator']['ram_cache_hits']==0
    same_score(score(combined,cur,locks,rem,apps,costs,seen),f['score']);close(s['phi'],f['score']['phi']);close(s['relative_to_F'],0.)
    assert s['counts']['response_queries']==s['counts']['response_hits']+s['counts']['response_misses']
    assert sum(s['timing'][k] for k in ('f_reference','f_quota','D'))<=s['candidate_seconds']+1e-6
    return combined

def check_r4_selection(r,start,nodes,apps,response,costs):
    p=r['plan'];witness=r['lock_repaired_gpu_plan'];cur=r['current'];locks=r['locks'];rem=r['lock_remaining'];seen=set(r['started']);s=r['selection']
    smart_round(r,start,nodes)
    expected=reference_check(witness,r['reference'],nodes,apps,response,cur,locks,rem,costs,seen)
    assert all(p[k]['node']==expected[k]['node'] for k in p)
    labels={'SIA-SMART-P':['P'],'CAPRA-FK':['F','K'],'CAPRA':['F','K','R']}[start['method']]
    assert [c['label'] for c in s['candidates']]==labels
    assert s['r_calls']==int('R' in labels) and s['r_skipped']==('R' not in labels)
    traces=s['allocator'].get('ram_traces',[])
    for i,t in enumerate(traces):assert t['trace_id']==i;verify_trace(t,nodes[t['node']],apps,response,locks)
    valid=[]
    for c in s['candidates']:
        if not c['feasible']:assert c['label'] in ('K','R') and c['reason'];continue
        a=c['allocations'];check_alloc(p,a,nodes,apps,response,locks)
        assert stable(c['mapping_before'],nodes,cur,locks,rem,apps,costs,seen)==a
        same_score(score(a,cur,locks,rem,apps,costs,seen),c['score'])
        if c['label'] in ('F','P'):assert all(a[k]['node']==p[k]['node'] for k in p)
        if start['method']=='SIA-SMART-P':
            assert c['quota']=={} and not traces
            for k,x in a.items():
                if k not in locks:
                    n=nodes[x['node']];close(x['cpu'],n['cpu']*x['gpus']/n['gpus']);close(x['ram'],n['ram']*x['gpus']/n['gpus']);close(x['rho'],1.)
        else:
            for nid,meta in c['quota'].items():
                t=traces[meta['ram_trace_id']];assert t['node']==nid and t['final']=={k:x for k,x in c['mapping_before'].items() if x['node']==nid}
        valid.append(c)
    winner=valid[0]
    for c in valid[1:]:
        a,b=c['score'],winner['score']
        if a['phi']>b['phi']+EPS or (abs(a['phi']-b['phi'])<=EPS and (a['total_delay']<b['total_delay']-EPS or (abs(a['total_delay']-b['total_delay'])<=EPS and a['changes']<b['changes']))):winner=c
    assert s['selected']==winner['label'] and r['allocations']==winner['allocations']
    return winner['allocations']

def distribution(values):
    return dict(n=len(values),median=float(np.quantile(values,.5)),p95=float(np.quantile(values,.95)),p99=float(np.quantile(values,.99)),max=max(values)) if values else None

def audit_records(directory,historical=False):
    """No writes: independently derive all values from sealed or unsealed records."""
    began=time.perf_counter();d=Path(directory);start=load(d/'start.json');term=load(d/'termination.json')
    if historical:
        assert start['version']=='CAPRA_V2_PRESSURE_R4' and start['method'] in ('SIA-SMART-P','CAPRA-FK','CAPRA')
        assert start['base_commit']=='5af0bdb6b86b797225908f717b5b9324cd48a539';smart_start(start)
    else:
        assert start['version']==VERSION and start['phase']=='FORMAL' and start['algorithm_base_commit']==BASE and start['inherited_direct_parent']==R4
        assert start['method'] in ('CAPRA-F-Only','CAPRA-Direct') and start['jobs_loaded_count']==start['expected_job_count']==80
        assert start['max_jobs'] is None and start['max_rounds']==6000
    assert start['max_jobs'] is None and start['interval']==60 and start['horizon']==180 and start['seed']==0 and not start['neutral']
    assert start['numeric_environment']==NUMERIC
    assert (start['python'],start['numpy'],start['scipy'],start['cvxpy'])==('3.10.10','1.26.4','1.13.1','1.6.5')
    paths={}
    for kind,entry in start['inputs'].items():
        p=(ROOT/entry['relative']).resolve();assert p.is_relative_to(ROOT) and sha(p)==entry['sha256'];paths[kind]=p
    rows=input_rows(paths['workload']);nodes={n['id']:n for n in load(paths['cluster'])};response=AuditResponses(paths['responses'])
    apps={r['name']:r['application'] for r in rows};costs=app_costs()
    for app,v in start['costs'].items():assert all(c==costs[app] for c in v.values())
    stats={r['name']:dict(job=r['name'],application=r['application'],arrival=float(r['time']),completion=None,waiting=0.,training=0.,recovery=0.,progress=0.,segments=0) for r in rows}
    node_rows=[];integrals={n:[0.,0.,0.] for n in nodes};last={};remaining={};seen=set();complete=set();last_end={};batches={};restore_kinds={};counts=Counter();selection=Counter();selection_nonempty=Counter();transitions=Counter();recovery_by_kind=Counter();times=[];times_all=[];components=defaultdict(list);aux=Counter();segment_checks=0;round_count=0
    with gzip.open(d/'events.jsonl.gz','rt',encoding='utf8') as f:
        for line in f:
            r=json.loads(line);assert r['round']==round_count and r['time']==60*round_count and r['version']==start['version'] and r['method']==start['method'];round_count+=1
            cur={k:a for k,a in last.items() if k not in complete};assert cur==r['current'] and set(r['started'])==seen
            locks={k:a for k,a in cur.items() if remaining.get(k,0)>EPS};assert locks==r['locks'] and r['lock_remaining']=={k:remaining[k] for k in locks}
            p=r['plan'];witness=r['lock_repaired_gpu_plan'];raw=r['raw_sia_plan'];assert set(p)==set(witness)==set(raw)
            for k,x in p.items():
                assert all(x[f]==witness[k][f] for f in ('name','gpu_type','gpus','nodes','atomic_bsz','accum_steps'))
                assert all(x[f]==raw[k][f] for f in ('gpu_type','gpus'))
            if historical:a=check_r4_selection(r,start,nodes,apps,response,costs)
            else:
                assert r['phase']=='FORMAL' and r['gpu_stage_calls']==r['commit_calls']==1 and r['provenance_fingerprint']==start['provenance_fingerprint']
                assert p==witness
                if start['method']=='CAPRA-Direct':a=audit_selection(witness,r['selection'],nodes,apps,response,cur,locks,r['lock_remaining'],start['costs'],seen)
                else:a=check_f_only(r,nodes,apps,response,costs)
                assert a==r['allocations'] and r['selection']['contract_checks'][-1]['where']=='BEFORE_COMMIT'
            use=check_alloc(p,a,nodes,apps,response,locks);assert use==r['node_usage']
            s=r['selection'];selection[s['selected']]+=1;counts['D_'+s.get('D_status','LEGACY')]+=1;times_all.append(r['decision_seconds'])
            if p:
                times.append(r['decision_seconds']);selection_nonempty[s['selected']]+=1;counts['nonempty_rounds']+=1
                counts['nonempty_D_'+s.get('D_status','LEGACY')]+=1
                if 'timing' in s:
                    for k,v in s['timing'].items():components[k].append(v)
                for k in ('gpu_stage_seconds','commit_seconds'):components[k].append(r[k])
            events={e['job']:e for e in r['transitions']};assert len(events)==len(r['transitions'])
            for k in set(cur)|set(p):
                x=a.get(k);old=cur.get(k);t=prediction(k,x,cur,locks,r['lock_remaining'],apps,costs,seen)
                if k in p:
                    assert r['commit_predictions'][k]==t;close(r['post_commit_remaining'][k],t['delay'])
                if t['kind'] not in ('unchanged','locked'):
                    e=events.pop(k);assert e['old']==old and e['new']==x and e['kind']==t['kind'];close(e['cost'],t['new_cost']);transitions[t['kind']]+=1
                if x is not None and t['gpu_change']:
                    remaining[k]=t['new_cost'];seen.add(k);counts['new_transition_cost_seconds']+=t['new_cost']
                    batch_equal=k in batches and batches[k]=={f:p[k][f] for f in ('atomic_bsz','accum_steps')}
                    if t['kind']=='start':category='first_start'
                    elif t['kind']=='resume':category='resume'
                    elif t['kind']=='migration' and old['gpu_type']==x['gpu_type'] and old['gpus']==x['gpus'] and batch_equal:category='pure_node_migration';counts['pure_node_migrations']+=1
                    else:category='GPU_type_shape_or_batch_with_node_change';counts['configuration_or_combined_changes']+=1
                    restore_kinds[k]=category
            assert not events
            for e in r['executions']:
                k=e['job'];st=stats[k];assert k not in complete and st['completion'] is None
                close(e['start'],last_end.get(k,st['arrival']));close(st['progress'],e['progress_before']);assert e['allocation']==a.get(k)
                close(e['end']-e['start'],e['waiting']+e['training']+e['recovery'])
                restore=min(remaining.get(k,0),e['end']-e['start']) if e['allocation'] else 0.;close(restore,e['recovery'])
                if e['allocation']:remaining[k]=max(0.,remaining.get(k,0)-restore)
                close(e['rescale_remaining'],remaining.get(k,0));recovery_by_kind[restore_kinds.get(k,'none')]+=restore
                close(sum(seg['seconds'] for seg in e['segments']),e['training']);last_progress=e['progress_before']
                if e['segments']:close(e['segments'][0]['start'],e['start']+restore)
                for seg in e['segments']:
                    x=e['allocation'];assert x is not None;close(seg['before'],last_progress)
                    expected=response.rho(apps[k],x['gpus'],x['cpu'],x['ram']);assert abs(seg['rho']-expected)<1e-9 and abs(x['rho']-expected)<1e-9
                    residual=seg['after']-seg['before']-seg['raw_rate']*seg['rho']*seg['seconds'];tolerance=.500001*seg['raw_rate']*seg['rho'] if seg['rounding'] else 1e-6
                    assert abs(residual)<=tolerance+1e-6,'RHO_ONCE_PROGRESS';last_progress=seg['after'];segment_checks+=1
                close(last_progress,e['progress_after']);assert e['progress_after']+1e-9>=e['progress_before']
                if e['allocation'] is None:assert e['training']==e['recovery']==0
                for name in ('waiting','training','recovery'):st[name]+=e[name]
                st.update(progress=e['progress_after'],completion=e['completion_time'],segments=st['segments']+len(e['segments']))
                if e['allocation']:
                    x=e['allocation'];duration=e['end']-e['start']
                    for i,name in enumerate(('gpus','cpu','ram')):integrals[x['node']][i]+=x[name]*duration
                    n=nodes[x['node']];g=x['gpus'];cp=n['cpu']*g/n['gpus'];mp=n['ram']*g/n['gpus'];train=e['training']
                    aux['training_seconds']+=train;aux['rho_seconds']+=train*x['rho'];aux['above_proportion_seconds']+=train*(x['rho']>response.rho(apps[k],g,cp,mp)+EPS)
                    cd=x['rho']-response.rho(apps[k],g,cp,x['ram']);md=x['rho']-response.rho(apps[k],g,x['cpu'],mp)
                    aux['CPU_conditional_rho_seconds']+=train*cd;aux['RAM_conditional_rho_seconds']+=train*md;aux['CPU_positive_training_seconds']+=train*(cd>EPS);aux['RAM_positive_training_seconds']+=train*(md>EPS)
                if e['completion_time'] is not None:complete.add(k)
                last_end[k]=e['end'];batches[k]=e['batch_after']
            assert r['completed']==len(complete) and r['total']==80
            if not historical:assert r['gpu_stage_seconds']+s['candidate_seconds']+r['commit_seconds']<=r['decision_seconds']+1e-6
            node_rows.extend(dict(round=r['round'],time=r['time'],node=n,gpus=use[n][0],cpu=use[n][1],ram=use[n][2]) for n in nodes);last=a
    assert term['rounds']==round_count and term['completed']==len(complete)
    all_done=len(complete)==80;valid=term['status']=='ALL_COMPLETE' and all_done;failed=term['status'] in ('IMPLEMENTATION_ERROR','AUDIT_ERROR')
    for k,st in stats.items():
        st['submitted']=st['arrival']<=term['simulated_seconds'];st['completed']=st['completion'] is not None;st['censored']=not st['completed'];st['jct']=st['completion']-st['arrival'] if st['completed'] else None
        if st['jct'] is not None:close(st['jct'],st['waiting']+st['training']+st['recovery'])
    jcts=[st['jct'] for st in stats.values()] if valid else []
    submitted=sum(st['submitted'] for st in stats.values());totals={k:sum(st[k] for st in stats.values()) for k in ('waiting','training','recovery')}
    training=aux['training_seconds'];summary=dict(version=start['version'],phase='FORMAL',method=start['method'],scenario=start.get('scenario',start.get('scenario_id')),execution_status='FAILED' if failed else ('COMPLETE' if valid else 'PARTIAL'),audit_status='FAIL' if failed else 'PASS',formal_performance_experiment='FAILED' if failed else ('COMPLETE' if valid else 'PARTIAL'),termination_reason=term['status'],expected_job_count=80,jobs_loaded_count=80,submitted_count=submitted,arrived_count=submitted,completed_count=len(complete),censored_count=80-len(complete),mean_jct=float(np.mean(jcts)) if jcts else None,median_jct=float(np.quantile(jcts,.5)) if jcts else None,p95_jct=float(np.quantile(jcts,.95)) if jcts else None,p99_jct=float(np.quantile(jcts,.99)) if jcts else None,makespan=max(st['completion'] for st in stats.values())-min(st['arrival'] for st in stats.values()) if valid else None,total_waiting=totals['waiting'] if valid else None,total_training=totals['training'] if valid else None,total_recovery=totals['recovery'] if valid else None,observed_prefix_totals=totals,rounds=round_count,decision_distribution=distribution(times),decision_all_rounds=distribution(times_all),component_times={k:distribution(v) for k,v in components.items()},selection_all_rounds=dict(selection),selection_nonempty_rounds=dict(selection_nonempty),counts=dict(counts),transitions=dict(transitions),actual_recovery_by_last_transition=dict(recovery_by_kind),node_allocated_resource_seconds=integrals,segment_checks=segment_checks,training_auxiliary_metrics={k:v/training for k,v in aux.items() if k!='training_seconds'} if training else {},actual_training_seconds=training,decision_wall_charged_to_JCT=False,quantile_definition='numpy.quantile(method=linear), q=.5/.95/.99',runner_body_wall_seconds=term['wall_seconds'],audit_recompute_wall_seconds=time.perf_counter()-began,result_origin='REUSED_R4' if historical else 'NEW_EXECUTION_R6',algorithm_base_commit=start.get('algorithm_base_commit'),actual_execution_head=start.get('actual_execution_head'))
    checks=dict(status='PASS' if not failed else 'FAIL',raw_rounds=round_count,segment_checks=segment_checks,method=start['method'],pure_selection_checks='R5 audit_selection' if start['method']=='CAPRA-Direct' else ('F_ONLY_NO_D' if start['method']=='CAPRA-F-Only' else 'FROZEN_R4_DEFINITION'),no_production_scheduler_calls=True,sealed_source_unchanged=True)
    return summary,list(stats.values()),node_rows,checks

def write_table(path,rows,fields):
    with Path(path).open('w',encoding='utf8',newline='') as f:w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)

def derive_and_write(directory):
    d=Path(directory).resolve();assert d.is_relative_to(RUN) and not (d/'evidence_hashes.json').exists(),'SEALED_CELL_MUST_NOT_BE_REWRITTEN'
    summary,jobs,nodes,checks=audit_records(d)
    write_table(d/'per_job.csv',jobs,list(jobs[0]));write_table(d/'node_resources.csv',nodes,['round','time','node','gpus','cpu','ram'])
    dump(d/'summary.json',summary);dump(d/'independent_audit.json',checks)
    names=('start.json','events.jsonl.gz','termination.json','summary.json','per_job.csv','node_resources.csv','independent_audit.json')
    dump(d/'evidence_hashes.json',{p:sha(d/p) for p in names})
    return summary
