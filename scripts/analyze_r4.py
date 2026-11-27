"""Independent read-only event/accounting analysis; all writes under R2 analysis."""
from collections import Counter,defaultdict
import csv,gzip,math
import numpy as np
from r4_utils import *
from capra.response import Responses
from capra.inputs import resolve_inputs
OUT=RUN/'analysis'
SCENARIOS=('w2_dense_original','w6_dense_original','w2_dense_cm')
def table(path,rows,fields=None):
    if not rows:return
    with Path(path).open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fields or list(rows[0]),extrasaction='ignore');w.writeheader();w.writerows(rows)
def dist(values):
    if not values:return None
    return dict(n=len(values),median=float(np.median(values)),p95=float(np.quantile(values,.95)),p99=float(np.quantile(values,.99)),max=max(values),mean=float(np.mean(values)),gt5_count=sum(v>5 for v in values),gt5_fraction=sum(v>5 for v in values)/len(values))
def near(a,b):assert abs(a-b)<=1e-6,(a,b)
def read_cell(source):
    d=ROOT/source['output'];start=load(d/'start.json');summary=load(d/'summary.json');paths=resolve_inputs(start)
    with paths['workload'].open(encoding='utf8',newline='') as f:rows=list(csv.DictReader(f))
    if start['max_jobs'] is not None:rows=rows[:start['max_jobs']]
    nodes={n['id']:n for n in load(paths['cluster'])};response=Responses(ROOT/source['target_responses'] if source.get('target_responses') else paths['responses'])
    stats={r['name']:dict(job=r['name'],application=r['application'],arrival=float(r['time']),waiting=0.,training=0.,recovery=0.,progress=0.,completion=None) for r in rows}
    active=0;rounds=0;timing=defaultdict(list);weighted=Counter();selected=Counter();feasible=Counter();failures=Counter();transition=Counter();pure=0;gpu_changes=0
    phi=defaultdict(list);rawrho=defaultdict(list);ram=Counter();all_r_calls=0;new_r_calls_available=False;residual=[];point_rows=[];candidate_rows=[]
    allocated=defaultdict(Counter);gpu_trace=__import__('hashlib').sha256()
    with gzip.open(d/'events.jsonl.gz','rt',encoding='utf8') as f:
        for line in f:
            r=__import__('json').loads(line);rounds+=1;timing['decision_all_rounds'].append(r['decision_seconds'])
            gpu_trace.update((__import__('json').dumps(dict(plan=r['plan'],allocations={k:{f:x[f] for f in ('node','gpu_type','gpus')} for k,x in r['allocations'].items()}),sort_keys=True)+'\n').encode())
            chosen=next(c for c in r['selection']['candidates'] if c['label']==r['selection']['selected'])
            extra={};legacy_ram={};astats=r['selection']['allocator']
            traces=astats.get('ram_traces',[])
            if source['allocator_mode']=='ram_slack_v1':
                for meta in chosen['quota'].values():
                    tr=traces[meta['ram_trace_id']];ram['selected_updates']+=tr['ram_steps']
                    for k,x in tr['initial'].items():legacy_ram[k]=x['ram'];extra[k]=max(0,tr['final'][k]['ram']-x['ram'])
            if r['plan']:
                active+=1;selected[chosen['label']]+=1;timing['decision'].append(r['decision_seconds'])
                for field,key in [('gpu','gpu_stage_seconds'),('reference','reference_seconds'),('candidate_total','candidate_seconds'),('mapping_scoring_nested','mapping_scoring_seconds'),('commit','commit_seconds')]:timing[field].append(r[key])
                if 'candidate_timings' in r['selection']:
                    new_r_calls_available=True
                    for label,value in r['selection']['candidate_timings'].items():
                        if value is not None:timing[label].append(value)
                    all_r_calls+=r['selection']['r_calls']
                    timing['ram_repair_nested'].append(astats.get('ram_repair_seconds',0.))
                    timing['node_pair_generation_nested'].append(astats['generation_seconds'])
                    if 'r4_allocator_seconds' in astats:
                        assert 0<=astats['r4_allocator_seconds']<=r['selection']['candidate_seconds']+1e-6
                        timing['allocator_inclusive_nested'].append(astats['r4_allocator_seconds'])
                for field in ('node_calls','node_cache_hits','generated_pairs','upgrades'):ram['legacy_'+field]+=astats[field]
                for field in ('ram_calls','ram_cache_hits','ram_requests','ram_steps','ram_step_bound','ram_candidates'):ram[field]+=astats.get(field,0)
                reference=next((c for c in r['selection']['candidates'] if c['label']=='F'),None);fphi=reference['score']['phi'] if reference else None;frho=sum(a['rho'] for a in reference['allocations'].values()) if reference else None
                for c in r['selection']['candidates']:
                    if not c['feasible']:failures[c['label']+':'+c['reason']]+=1;continue
                    feasible[c['label']]+=1;pd=c['score']['phi']-fphi if reference else None;rd=sum(a['rho'] for a in c['allocations'].values())-frho if reference else None
                    if reference:phi[c['label']].append(pd);rawrho[c['label']].append(rd)
                    candidate_rows.append(dict(round=r['round'],label=c['label'],selected=c['label']==chosen['label'],phi=c['score']['phi'],sum_rho=sum(a['rho'] for a in c['allocations'].values()),phi_minus_F=pd,sum_rho_minus_F=rd,total_delay=c['score']['total_delay']))
            for e in r['transitions']:
                transition[e['kind']]+=1
                if e['old'] and e['new']:
                    same=(e['old']['gpu_type'],e['old']['gpus'])==(e['new']['gpu_type'],e['new']['gpus'])
                    pure+=e['kind']=='migration' and same;gpu_changes+=not same
            # Continuous, same-CPU one-target RAM opportunities; never call old pool_ram.
            for k,a in r['allocations'].items():
                if k in r['locks']:continue
                n=nodes[a['node']];upper=min(a['gpus']*max(response.data['ram_axis']),n['ram']-math.fsum(x['ram'] for j,x in r['allocations'].items() if x['node']==a['node'] and j!=k))
                rho=response.rho(stats[k]['application'],a['gpus'],a['cpu'],upper)
                if upper>a['ram']+1e-9 and rho>a['rho']+1e-9:
                    residual.append(dict(round=r['round'],time=r['time'],job=k,application=stats[k]['application'],node=a['node'],gpus=a['gpus'],cpu=a['cpu'],ram=a['ram'],rho=a['rho'],ram_upper=upper,rho_upper=rho,scope='One target independently, all others fixed; shared slack not summed'))
            for e in r['executions']:
                s=stats[e['job']];near(s['progress'],e['progress_before']);s['progress']=e['progress_after'];s['completion']=e['completion_time']
                near(e['end']-e['start'],e['waiting']+e['training']+e['recovery'])
                for field in ('waiting','training','recovery'):s[field]+=e[field]
                a=e['allocation']
                if a:
                    for field in ('gpus','cpu','ram'):allocated[a['node']][field]+=a[field]*(e['end']-e['start'])
                    ram['selected_extra_ram_gb_seconds_including_recovery']+=extra.get(e['job'],0.)*(e['end']-e['start'])
                if not e['training']:continue
                near(sum(seg['seconds'] for seg in e['segments']),e['training']);n=nodes[a['node']];g=a['gpus'];cp=n['cpu']*g/n['gpus'];mp=n['ram']*g/n['gpus']
                rho=response.rho(s['application'],g,a['cpu'],a['ram']);near(rho,a['rho']);prop=response.rho(s['application'],g,cp,mp)
                cd=rho-response.rho(s['application'],g,cp,a['ram']);md=rho-response.rho(s['application'],g,a['cpu'],mp);duration=e['training']
                for key,value in [('rho',rho),('relative_rho',rho/prop),('above_prop',rho>prop+1e-9),('cpu_conditional',cd),('ram_conditional',md),('cpu_positive',cd>1e-9),('ram_positive',md>1e-9)]:weighted[key]+=duration*value
                weighted['training']+=duration;weighted['ram_extra_this_round_training']+=duration*(extra.get(e['job'],0)>1e-9);weighted['extra_ram_gb']+=duration*extra.get(e['job'],0)
                nonaxis=all(abs(a['ram']-z*g)>1e-7 for z in response.data['ram_axis']) and abs(a['ram']-mp)>1e-7
                weighted['intermediate_ram_training']+=duration*nonaxis
                if extra.get(e['job'],0)>1e-9 or nonaxis:
                    point_rows.append(dict(round=r['round'],job=e['job'],application=s['application'],node=a['node'],gpus=g,cpu=a['cpu'],ram=a['ram'],rho=rho,training_seconds=duration,
                        extra_ram_this_supplement=extra.get(e['job'],0),legacy_final_ram=legacy_ram.get(e['job']),nonaxis_ram=nonaxis))
    completed=[s for s in stats.values() if s['completion'] is not None];all_done=len(completed)==len(stats)
    for s in stats.values():
        s['jct']=s['completion']-s['arrival'] if s['completion'] is not None else None
        if s['jct'] is not None:near(s['jct'],s['waiting']+s['training']+s['recovery'])
    with (d/'per_job.csv').open(encoding='utf8',newline='') as f:logged={s['job']:s for s in csv.DictReader(f)}
    for k,s in stats.items():
        for field in ('waiting','training','recovery','progress'):near(s[field],float(logged[k][field]))
        if s['jct'] is not None:near(s['jct'],float(logged[k]['jct']))
    jcts=[s['jct'] for s in completed]
    if all_done:
        for field,value in [('mean_jct',np.mean(jcts)),('p50_jct',np.quantile(jcts,.5)),('p95_jct',np.quantile(jcts,.95)),('p99_jct',np.quantile(jcts,.99))]:near(summary[field],float(value))
    else:
        for field in ('mean_jct','p50_jct','p95_jct','p99_jct','makespan'):assert summary[field] is None
    if all_done:near(summary['makespan'],max(s['completion'] for s in completed)-min(s['arrival'] for s in stats.values()))
    for field in ('waiting','training','recovery'):near(summary['mean_'+field],np.mean([s[field] for s in stats.values()]))
    apps={app:dict(jobs=sum(s['application']==app for s in stats.values()),mean_jct=float(np.mean([s['jct'] for s in stats.values() if s['application']==app])) if all_done else None) for app in sorted({s['application'] for s in stats.values()})}
    total=weighted['training'];training={k:v/total for k,v in weighted.items() if k!='training'}
    metrics=dict(id=source['id'],source=source,summary=summary,application_results=apps,training=training,active_rounds=active,all_rounds=rounds,
        timing={k:dist(timing[k]) for k in sorted(set(timing)|{'decision','decision_all_rounds'})},candidate_feasible=dict(feasible),candidate_selected=dict(selected),candidate_failures=dict(failures),
        phi_minus_F={k:dict(dist(v),positive=sum(x>1e-9 for x in v),negative=sum(x<-1e-9 for x in v)) for k,v in phi.items()},
        sum_rho_minus_F={k:dict(dist(v),positive=sum(x>1e-9 for x in v),negative=sum(x<-1e-9 for x in v)) for k,v in rawrho.items()},
        transitions=dict(transition),pure_node_migrations=pure,other_gpu_configuration_changes=gpu_changes,actual_recovery=sum(s['recovery'] for s in stats.values()),
        r_calls_active=all_r_calls if new_r_calls_available else None,component_timing_available=new_r_calls_available,ram=dict(ram),
        residual_ram_opportunity_certificates=len(residual),residual_ram_rounds=len({x['round'] for x in residual}),gpu_node_trace_sha256=gpu_trace.hexdigest(),
        input_hashes={k:(sha(ROOT/source['target_responses']) if k=='responses' and source.get('target_responses') else v['sha256']) for k,v in start['inputs'].items()},costs=start['costs'],allocation_resource_seconds={k:dict(v) for k,v in allocated.items()})
    out=OUT/'cells'/source['id'];out.mkdir(parents=True,exist_ok=True)
    dump(out/'metrics.json',metrics);dump(out/'residual_ram_opportunities.json',residual);table(out/'candidate_scores.csv',candidate_rows);table(out/'ram_training_points.csv',point_rows)
    table(out/'per_job_recomputed.csv',list(stats.values()))
    return metrics,stats
def compare(label,phase,scenario,method,baseline,a,b,sa,sb):
    assert a['input_hashes']==b['input_hashes'] and a['costs']==b['costs'],'UNFAIR_INPUT_OR_COST_COMPARISON'
    rows=[]
    for k,x in sa.items():
        y=sb[k];assert x['application']==y['application'] and x['arrival']==y['arrival']
        if x['jct'] is None or y['jct'] is None:continue
        ratio=x['jct']/y['jct'];delta=x['jct']-y['jct'];direction='fast' if delta<-1e-7 else ('slow' if delta>1e-7 else 'tie')
        row=dict(comparison=label,phase=phase,scenario=scenario,method=method,baseline=baseline,job=k,application=x['application'],method_jct=x['jct'],baseline_jct=y['jct'],delta_jct=delta,relative_baseline_jct_ratio=ratio,direction=direction)
        for part in ('waiting','training','recovery'):row['method_'+part]=x[part];row['baseline_'+part]=y[part]
        rows.append(row)
    all_done=a['summary']['completed']==b['summary']['completed']==80
    result=dict(comparison=label,phase=phase,scenario=scenario,method=method,baseline=baseline,method_id=a['id'],baseline_id=b['id'],paired_jobs=len(rows),
        fast=sum(x['direction']=='fast' for x in rows),tie=sum(x['direction']=='tie' for x in rows),slow=sum(x['direction']=='slow' for x in rows),
        ratio_p95=float(np.quantile([x['relative_baseline_jct_ratio'] for x in rows],.95)) if all_done else None,ratio_max=max((x['relative_baseline_jct_ratio'] for x in rows),default=None) if all_done else None,
        worst_ratio_case=max(rows,key=lambda x:x['relative_baseline_jct_ratio']) if rows else None,worst_absolute_case=max(rows,key=lambda x:x['delta_jct']) if rows else None)
    for field in ('mean_jct','p50_jct','p95_jct','p99_jct','makespan'):
        x,y=a['summary'][field],b['summary'][field];result[field+'_improvement_percent']=100*(1-x/y) if all_done else None
    for field in ('waiting','training','recovery'):result['mean_'+field+'_difference']=a['summary']['mean_'+field]-b['summary']['mean_'+field] if all_done else None
    result['decision_p95_method']=a['summary']['decision_p95'];result['decision_p95_baseline']=b['summary']['decision_p95']
    return result,rows


def pressure(source,metrics,stats):
    import re
    d=ROOT/source['output'];start=load(d/'start.json');paths=resolve_inputs(start);nodes={x['id']:x for x in load(paths['cluster'])}
    rows=list(csv.DictReader(paths['workload'].open(encoding='utf8',newline='')));arrivals={x['name']:float(x['time']) for x in rows}
    if not all(x['completion'] is not None for x in stats.values()):return dict(status='INCOMPLETE',pressure_integrals=None)
    lo=min(arrivals.values());hi=max(x['completion'] for x in stats.values());window=hi-lo
    scopes={'GLOBAL':list(nodes)}
    for typ in sorted({x['gpu_type'] for x in nodes.values()}):scopes['TYPE:'+typ]=[n for n,x in nodes.items() if x['gpu_type']==typ]
    for n in nodes:scopes['NODE:'+n]=[n]
    caps={s:{f:sum(nodes[n][f] for n in ns) for f in ('gpus','cpu','ram')} for s,ns in scopes.items()}
    deltas=defaultdict(lambda:defaultdict(Counter));integrals=defaultdict(Counter);full=defaultdict(Counter);timeline=[];complete=set();smart=Counter();smart_times=[];repair_jobs=Counter();mip_rounds=[]
    apps={x['name']:x['application'] for x in rows};profile=Responses(ROOT/source['target_responses'] if source.get('target_responses') else paths['responses']);pref_cache={};demand=defaultdict(list);aux_limits=Counter()
    with gzip.open(d/'events.jsonl.gz','rt',encoding='utf8') as f:
        for line in f:
            r=__import__('json').loads(line)
            ready={k for k,t in arrivals.items() if t<=r['time'] and k not in complete};queued=ready-set(r['plan']);x=dict(round=r['round'],time=r['time'],arrived=sum(t<=r['time'] for t in arrivals.values()),completed_before=len(complete),active_ready_jobs=len(ready),selected_jobs=len(r['plan']),unscheduled_ready_queue=len(queued),recovering_locks=len(r['locks']),decision_seconds=r['decision_seconds'])
            for typ in sorted({n['gpu_type'] for n in nodes.values()}):
                ns=scopes['TYPE:'+typ]
                for i,field in enumerate(('gpus','cpu','ram')):x[typ+'_'+field+'_at_decision']=sum(r['node_usage'][n][i] for n in ns)
            if r['plan']:
                wanted=defaultdict(Counter)
                for job,a in r['allocations'].items():
                    n=nodes[a['node']];g=a['gpus'];key=(apps[job],g,n['gpu_type'])
                    if key not in pref_cache:
                        # Static frozen-table preference, not a layout/state search or
                        # an allocator call; there is no write to scheduler/model state.
                        from types import SimpleNamespace
                        c,m=profile.preferred(apps[job],g,SimpleNamespace(**n));rho=profile.rho(apps[job],g,c,m);prop=profile.rho(apps[job],g,n['cpu']*g/n['gpus'],n['ram']*g/n['gpus']);data=profile.data['profiles'][apps[job]];overall=max(max(v) for v in data['table'])/data['reference']
                        pref_cache[key]=(c,m,rho,prop,overall)
                    c,m,rho,prop,overall=pref_cache[key];wanted[a['node']]['cpu']+=c;wanted[a['node']]['ram']+=m
                    aux_limits['selected_job_rounds']+=1;aux_limits['has_unrealized_within_node_rho_gain_job_rounds']+=rho>a['rho']+1e-9;aux_limits['GPU_shape_caps_all_aux_gain_job_rounds']+=rho<=prop+1e-9 and overall>prop+1e-9
                for scope,ns in scopes.items():
                    for field in ('cpu','ram'):demand[(scope,field)].append(sum(wanted[n][field] for n in ns)/caps[scope][field])
            timeline.append(x)
            if r['gpu_stage']['solver_status']!='NO_JOBS':mip_rounds.append((r['round'],bool(r['plan'])))
            for c in r['gpu_stage'].get('smart_records',[]):
                smart['raw_retained_job_rounds']+=len(c['retained']);smart['raw_evicted_events']+=len(c['evicted']);smart['raw_replaced_job_rounds']+=len(c['replaced'])
            if r['plan'] and 'smart_seconds' in r['gpu_stage']:smart_times.append(r['gpu_stage']['smart_seconds'])
            if r['gpu_stage']['repairs']:
                smart['shared_witness_repair_rounds']+=1
                for k,p in r['raw_sia_plan'].items():
                    if p['node']!=r['lock_repaired_gpu_plan'][k]['node']:repair_jobs[k]+=1
            for e in r['executions']:
                a=e['allocation']
                if a:
                    for t,sign in ((e['start'],1),(e['end'],-1)):
                        for field in ('gpus','cpu','ram'):deltas[t][a['node']][field]+=sign*a[field]
                if e['completion_time'] is not None:complete.add(e['job'])
    use={n:Counter() for n in nodes};previous=lo
    for t,changes in sorted(deltas.items()):
        left=max(previous,lo);right=min(t,hi);duration=max(0.,right-left)
        if duration:
            for scope,ns in scopes.items():
                for field in ('gpus','cpu','ram'):
                    value=sum(use[n][field] for n in ns);assert -1e-5<=value<=caps[scope][field]+1e-5
                    integrals[scope][field]+=max(0,value)*duration
                    threshold=1. if field=='gpus' else .95
                    if value>=threshold*caps[scope][field]-1e-7:full[scope][field]+=duration
        for n,values in changes.items():use[n].update(values)
        previous=t
    output=[]
    for scope in scopes:
        output.append(dict(scope=scope,**{f+'_allocated_fraction':integrals[scope][f]/(caps[scope][f]*window) for f in ('gpus','cpu','ram')},**{f+'_high_capacity_time_fraction':full[scope][f]/window for f in ('gpus','cpu','ram')},window_seconds=window))
    global_row=next(x for x in output if x['scope']=='GLOBAL')
    for field in ('gpus','cpu','ram'):near(global_row[field+'_allocated_fraction'],metrics['summary']['allocated_resource_fraction'][field])
    durations={k:sum(s[k] for s in stats.values())/window for k in ('waiting','training','recovery')}
    avg_active=sum(s['jct'] for s in stats.values())/window;near(avg_active,sum(durations.values()))
    # Existing upstream printed intervals are measured values, not GPU-stage subtraction.
    log=d.parent/(d.name+'.stdout.log');mip=[];mapping_valid=False
    if log.exists():
        found=re.findall(r'Solver took: ([0-9.]+)ms = ([0-9.]+)ms \(setup\) \+ ([0-9.]+)ms \(solve\)',log.read_text(encoding='utf8',errors='replace'))
        mapping_valid=len(found)==len(mip_rounds)
        if mapping_valid:mip=[dict(round=i,nonempty_plan=active,total_seconds=float(a)/1000,setup_seconds=float(b)/1000,solve_seconds=float(c)/1000) for (i,active),(a,b,c) in zip(mip_rounds,found)]
    timings=dict(mip_total=dist([x['total_seconds'] for x in mip if x['nonempty_plan']]),mip_setup=dist([x['setup_seconds'] for x in mip if x['nonempty_plan']]),mip_solve=dist([x['solve_seconds'] for x in mip if x['nonempty_plan']]),mip_all_calls=dist([x['total_seconds'] for x in mip]),smart=dist(smart_times),audit_total_seconds=metrics['summary'].get('audit_seconds'),MIP_stdout_count_matches=mapping_valid,MIP_expected=len(mip_rounds),timing_scope='MIP printed setup/solve intervals rounded0.01ms; primary components use nonempty-plan rounds, all MIP calls separately. GPU stage includes preparation/MIP/smart. Allocator, R, identity+score and RAM have nested boundaries; do not sum.')
    demand_summary={scope:{field:dict(mean=float(np.mean(demand[scope,field])),p95=float(np.quantile(demand[scope,field],.95)),max=max(demand[scope,field]),over_capacity_decision_fraction=sum(v>1+1e-9 for v in demand[scope,field])/len(demand[scope,field])) for field in ('cpu','ram')} for scope in scopes}
    result=dict(status='PASS',allocation_scope='Allocation capacity-time including recovery; not hardware busy utilization',window_start=lo,window_end=hi,window_seconds=window,resources=output,global_resources=global_row,average_active_ready_jobs=avg_active,average_waiting_queue_jobs=durations['waiting'],average_training_jobs=durations['training'],average_recovering_jobs=durations['recovery'],peak_active_ready_jobs=max(x['active_ready_jobs'] for x in timeline),peak_unscheduled_ready_queue=max(x['unscheduled_ready_queue'] for x in timeline),queue_scope='Global ready-but-unscheduled queue; waiting jobs have no assigned GPU pool, never arbitrarily split by type. Means from exact time ledgers, peaks at decision samples.',timings=timings,smart_counts=dict(smart),smart_repair_affected_jobs=dict(repair_jobs),profile_preferred_aux_demand=demand_summary,auxiliary_limits=dict(aux_limits),aux_demand_scope='Decision-snapshot sum of each selected job frozen-table preferred legal-within-single-node quota / capacity; not original trace request, realized reservation, or proof of obtainable net gain. GPU-shape ceiling flag compares best legal response under current GPU shape with proportional response and global table maximum.')
    out=OUT/'cells'/source['id'];dump(out/'pressure_metrics.json',result);table(out/'queue_resource_timeline.csv',timeline);table(out/'resource_capacity_time.csv',output);table(out/'upstream_mip_times.csv',mip)
    return result

def main():
    began=time.perf_counter();OUT.mkdir(exist_ok=True);physical=load(RUN/'results.json');sources=[]
    for r in physical:
        if r.get('state')=='COMPLETE_PASS':sources.append(dict(id=r['scenario']+'/'+r['method'],phase='R4',scenario=r['scenario'],profile=r['profile'],method=r['method'],workload_id=r['workload_id'],source_workload_id=r['source_workload_id'],allocator_mode=r['allocator_mode'],phase_version=r['phase_version'],result_origin='NEW_EXECUTION',executed=True,reused=False,source_commit=None,base_commit=BASE,source_snapshot_sha256=r['source_snapshot_sha256'],output=r['output'],physical_index=r['index'],timing_scope='Observed actual R4 execution'))
    history=load(ROOT/'runs/smart_holdout_r3/analysis/source_index.json')
    for h in history:
        if h['phase']=='B' and h['method'] in ('SIA-SMART-P','CAPRA-FK','CAPRA'):
            sources.append(dict(h,id='HISTORY/R3/'+h['id'],phase='R3_REFERENCE',result_origin='HISTORICAL_REFERENCE',original_result_origin=h['result_origin'],executed=False,reused=True,source_commit='5af0bdb6b86b797225908f717b5b9324cd48a539',timing_scope='Historical source observed, including original timing for equivalence alias'))
    metrics={};jobs={};flat=[];integrity={};resources=[]
    for src in sources:
        d=ROOT/src['output'];src['files_sha256']={n:sha(d/n) for n in ('start.json','events.jsonl.gz','summary.json','per_job.csv','node_resources.csv')}
        for n,h in src['files_sha256'].items():integrity[(d/n).relative_to(ROOT).as_posix()]=h
        x,j=read_cell(src);x['pressure']=pressure(src,x,j)
        if (d/'process.json').exists():x['summary']['wall_seconds']=load(d/'process.json')['process_wall_seconds']
        metrics[src['id']]=x;jobs[src['id']]=j
        flat.append(dict(id=src['id'],phase=src['phase'],scenario=src['scenario'],profile=src['profile'],method=src['method'],display_method='CAPRA-FKR' if src['method']=='CAPRA' else src['method'],allocator_mode=src['allocator_mode'],result_origin=src['result_origin'],executed=src['executed'],timing_scope=src['timing_scope'],**{k:x['summary'].get(k) for k in ('status','submitted','completed','total','censored','mean_jct','p50_jct','p95_jct','p99_jct','makespan','mean_waiting','mean_training','mean_recovery','decision_median','decision_p95','decision_max','wall_seconds','audit_seconds')},decision_p99=x['timing']['decision']['p99'],decision_gt5_count=x['timing']['decision']['gt5_count'],gpu_allocated_fraction=x['pressure']['global_resources']['gpus_allocated_fraction'],cpu_allocated_fraction=x['pressure']['global_resources']['cpu_allocated_fraction'],ram_allocated_fraction=x['pressure']['global_resources']['ram_allocated_fraction'],average_active_jobs=x['pressure']['average_active_ready_jobs'],average_queue_jobs=x['pressure']['average_waiting_queue_jobs'],peak_queue=x['pressure']['peak_unscheduled_ready_queue']))
        resources += [dict(id=src['id'],scenario=src['scenario'],method=src['method'],result_origin=src['result_origin'],**v) for v in x['pressure']['resources']]
        print(__import__('json').dumps(dict(event='RAW_ANALYZED',id=src['id'],mean=x['summary']['mean_jct'],gpu=x['pressure']['global_resources']['gpus_allocated_fraction'])),flush=True)
    comparisons=[];pairs=[]
    for w in (7,8):
        for profile in ('original','cm'):
            scenario=f'saturn{w}_dense05_{profile}'
            for a,b in [('CAPRA-FK','SIA-SMART-P'),('CAPRA','SIA-SMART-P'),('CAPRA','CAPRA-FK')]:
                ida=scenario+'/'+a;idb=scenario+'/'+b
                if ida in metrics and idb in metrics:
                    c,p=compare(a+'/'+b,'R4',scenario,a,b,metrics[ida],metrics[idb],jobs[ida],jobs[idb]);comparisons.append(c);pairs+=p
    sensitivity=[]
    for src in sources:
        if src['phase']!='R4':continue
        old=next((s for s in sources if s['phase']=='R3_REFERENCE' and s['workload_id']==src['source_workload_id'] and s['method']==src['method'] and s['profile'].lower()==src['profile']),None)
        if old is None:continue
        a,b=metrics[src['id']],metrics[old['id']];assert a['input_hashes']['cluster']==b['input_hashes']['cluster'] and a['input_hashes']['responses']==b['input_hashes']['responses'] and a['costs']==b['costs']
        for k in jobs[src['id']]:assert jobs[src['id']][k]['application']==jobs[old['id']][k]['application']
        row=dict(scenario=src['scenario'],method=src['method'],R4_id=src['id'],R3_id=old['id'],scope='Scenario pressure sensitivity, not algorithm contribution or independent sample')
        for field in ('mean_jct','p95_jct','p99_jct','makespan','mean_waiting','mean_training','mean_recovery'):
            row['R3_'+field]=b['summary'][field];row['R4_'+field]=a['summary'][field]
        for scope in ('GLOBAL','TYPE:aws','TYPE:dgx-ext','TYPE:rtx'):
            ar=next(x for x in a['pressure']['resources'] if x['scope']==scope);br=next(x for x in b['pressure']['resources'] if x['scope']==scope)
            for field in ('gpus','cpu','ram'):
                row[scope+'_'+field+'_R3']=br[field+'_allocated_fraction'];row[scope+'_'+field+'_R4']=ar[field+'_allocated_fraction'];row[scope+'_'+field+'_delta_percentage_points']=100*(ar[field+'_allocated_fraction']-br[field+'_allocated_fraction'])
        row['queue_R3']=b['pressure']['average_waiting_queue_jobs'];row['queue_R4']=a['pressure']['average_waiting_queue_jobs'];row['active_R3']=b['pressure']['average_active_ready_jobs'];row['active_R4']=a['pressure']['average_active_ready_jobs'];sensitivity.append(row)
    for p,h in integrity.items():assert sha(ROOT/p)==h,('RAW_CHANGED',p)
    dump(OUT/'source_index.json',sources);table(OUT/'source_index.csv',[{k:v for k,v in s.items() if k!='files_sha256'} for s in sources],sorted({k for s in sources for k in s if k!='files_sha256'}))
    dump(OUT/'metrics.json',list(metrics.values()));dump(OUT/'results.json',flat);table(OUT/'results.csv',flat)
    dump(OUT/'comparisons.json',comparisons);table(OUT/'comparisons.csv',comparisons,[k for k in comparisons[0] if k not in ('worst_ratio_case','worst_absolute_case')] if comparisons else [])
    table(OUT/'paired_jobs.csv',pairs);table(OUT/'scenario_sensitivity.csv',sensitivity);dump(OUT/'scenario_sensitivity.json',sensitivity);table(OUT/'resource_pressure.csv',resources)
    dump(OUT/'worst_cases.json',[{k:c[k] for k in ('scenario','method','baseline','worst_ratio_case','worst_absolute_case')} for c in comparisons])
    dump(RUN/'source_index.json',sources);dump(OUT/'raw_integrity.json',dict(status='PASS',files_sha256=integrity,new_complete_jobs=sum(x.get('completed',0) for x in physical if x.get('state')=='COMPLETE_PASS'),historical_reference_rows=sum(s['phase']=='R3_REFERENCE' for s in sources),no_new_simulation=True))
    dump(OUT/'analysis_receipt.json',dict(status='PASS',wall_seconds=time.perf_counter()-began,new_cells=sum(s['phase']=='R4' for s in sources),historical_cells=sum(s['phase']=='R3_REFERENCE' for s in sources),comparisons=len(comparisons),simulation_calls=0,additional_state_search_calls=0))
    print('R4_READ_ONLY_ANALYSIS_PASS')
if __name__=='__main__':main()
