"""Independent read-only event/accounting analysis; all writes under R2 analysis."""
from collections import Counter,defaultdict
import csv,gzip,math
import numpy as np
from r2_utils import *
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
    return dict(n=len(values),median=float(np.median(values)),p95=float(np.quantile(values,.95)),max=max(values),mean=float(np.mean(values)),gt5_count=sum(v>5 for v in values),gt5_fraction=sum(v>5 for v in values)/len(values))
def near(a,b):assert abs(a-b)<=1e-6,(a,b)
def read_cell(source):
    d=ROOT/source['output'];start=load(d/'start.json');summary=load(d/'summary.json');paths=resolve_inputs(start)
    with paths['workload'].open(encoding='utf8',newline='') as f:rows=list(csv.DictReader(f))
    if start['max_jobs'] is not None:rows=rows[:start['max_jobs']]
    nodes={n['id']:n for n in load(paths['cluster'])};response=Responses(paths['responses'])
    stats={r['name']:dict(job=r['name'],application=r['application'],arrival=float(r['time']),waiting=0.,training=0.,recovery=0.,progress=0.,completion=None) for r in rows}
    active=0;rounds=0;timing=defaultdict(list);weighted=Counter();selected=Counter();feasible=Counter();failures=Counter();transition=Counter();pure=0;gpu_changes=0
    phi=defaultdict(list);rawrho=defaultdict(list);ram=Counter();all_r_calls=0;new_r_calls_available=not source['reused'];residual=[];point_rows=[];candidate_rows=[]
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
                if not source['reused']:
                    for label,value in r['selection']['candidate_timings'].items():
                        if value is not None:timing[label].append(value)
                    all_r_calls+=r['selection']['r_calls']
                    timing['ram_repair_nested'].append(astats.get('ram_repair_seconds',0.))
                for field in ('node_calls','node_cache_hits','generated_pairs','upgrades'):ram['legacy_'+field]+=astats[field]
                for field in ('ram_calls','ram_cache_hits','ram_requests','ram_steps','ram_step_bound','ram_candidates'):ram[field]+=astats.get(field,0)
                reference=r['selection']['candidates'][0];fphi=reference['score']['phi'];frho=sum(a['rho'] for a in reference['allocations'].values())
                for c in r['selection']['candidates']:
                    if not c['feasible']:failures[c['label']+':'+c['reason']]+=1;continue
                    feasible[c['label']]+=1;pd=c['score']['phi']-fphi;rd=sum(a['rho'] for a in c['allocations'].values())-frho
                    phi[c['label']].append(pd);rawrho[c['label']].append(rd)
                    candidate_rows.append(dict(round=r['round'],label=c['label'],selected=c['label']==chosen['label'],phi=c['score']['phi'],phi_minus_F=pd,sum_rho_minus_F=rd,total_delay=c['score']['total_delay']))
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
        r_calls_active=all_r_calls if new_r_calls_available else None,legacy_component_timing_available=not source['reused'],ram=dict(ram),
        residual_ram_opportunity_certificates=len(residual),residual_ram_rounds=len({x['round'] for x in residual}),gpu_node_trace_sha256=gpu_trace.hexdigest(),
        input_hashes={k:v['sha256'] for k,v in start['inputs'].items()},costs=start['costs'],allocation_resource_seconds={k:dict(v) for k,v in allocated.items()})
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
def main():
    OUT.mkdir(exist_ok=True);sources=[];freeze=load(RUN/'freeze_receipt.json');new=load(RUN/'results.json')
    for scenario in SCENARIOS:
        for method in ('SIA-P','CAPRA-Fixed','CAPRA'):
            sources.append(dict(id=f'R1/{scenario}/{method}',phase='R1',phase_version='CAPRA_V2_SCENARIOS_R1',scenario=scenario,method=method,allocator_mode='none' if method=='SIA-P' else 'legacy',
                reused=True,source_commit=BASE,source_snapshot_sha256=None,output=f'runs/scenarios_r1/CAPRA_V2_SCENARIOS_R1/{scenario}/{method}'))
    for row in new:
        if (ROOT/row['output']/'summary.json').exists():
            sources.append(dict(id=f'{row["phase"]}/{row["scenario"]}/{row["method"]}',phase=row['phase'],phase_version=row['phase_version'],scenario=row['scenario'],method=row['method'],allocator_mode=row['allocator_mode'],reused=False,
                source_commit=None,source_snapshot_sha256=freeze['source_snapshot_sha256'],output=row['output']))
    metrics={};stats={};integrity={};flat=[]
    for source in sources:
        d=ROOT/source['output'];source['files_sha256']={name:sha(d/name) for name in ('start.json','events.jsonl.gz','per_job.csv','summary.json','node_resources.csv')}
        for name,h in source['files_sha256'].items():integrity[(d/name).relative_to(ROOT).as_posix()]=h
        x,s=read_cell(source);metrics[source['id']]=x;stats[source['id']]=s
        flat.append(dict(id=source['id'],phase=source['phase'],scenario=source['scenario'],method=source['method'],allocator_mode=source['allocator_mode'],reused=source['reused'],
            **{k:x['summary'].get(k) for k in ('status','completed','total','censored','mean_jct','p50_jct','p95_jct','p99_jct','makespan','mean_waiting','mean_training','mean_recovery','decision_median','decision_p95','decision_max','wall_seconds')},
            decision_gt5_count=(x['timing']['decision'] or {}).get('gt5_count',0),decision_gt5_fraction=(x['timing']['decision'] or {}).get('gt5_fraction',0)))
        print(__import__('json').dumps(dict(event='RAW_ANALYZED',id=source['id'],completed=x['summary']['completed'],ram_residual_rounds=x['residual_ram_rounds'])),flush=True)
    for p,h in integrity.items():assert sha(ROOT/p)==h,('ANALYSIS_CHANGED_RAW',p)
    comparisons=[];pairs=[]
    def add(label,phase,scenario,method,baseline,ida,idb):
        if ida not in metrics or idb not in metrics:return
        result,rows=compare(label,phase,scenario,method,baseline,metrics[ida],metrics[idb],stats[ida],stats[idb]);comparisons.append(result);pairs.extend(rows)
    stageA=[]
    for scenario in SCENARIOS:
        ids={m:f'{"A" if m in ("SIA-P-K","CAPRA-FK") else "R1"}/{scenario}/{m}' for m in ('SIA-P','CAPRA-Fixed','SIA-P-K','CAPRA-FK','CAPRA')}
        for method,i in ids.items():
            if i in metrics:stageA.append(next(r for r in flat if r['id']==i))
        for label,a,b in [('position_proportional','SIA-P-K','SIA-P'),('position_optimized','CAPRA-FK','CAPRA-Fixed'),('resource_matched_stability','CAPRA-FK','SIA-P-K'),('R_dynamic_increment','CAPRA','CAPRA-FK'),('full_vs_SIA','CAPRA','SIA-P'),('full_vs_Fixed','CAPRA','CAPRA-Fixed')]:add(label,'A',scenario,a,b,ids[a],ids[b])
    stageB=[];scenario='w2_dense_cm'
    for method in ('CAPRA-Fixed','CAPRA-FK','CAPRA'):
        old=f'{"A" if method=="CAPRA-FK" else "R1"}/{scenario}/{method}';newid=f'B/{scenario}/{method}'
        for i in (old,newid):
            if i in metrics:stageB.append(next(r for r in flat if r['id']==i))
        add('RAM_repair_before_after','B',scenario,method+'_repaired',method+'_legacy',newid,old)
    for a,b in [('CAPRA-FK','CAPRA-Fixed'),('CAPRA','CAPRA-FK'),('CAPRA','CAPRA-Fixed')]:add('repaired_same_version','B',scenario,a,b,f'B/{scenario}/{a}',f'B/{scenario}/{b}')
    dump(OUT/'source_index.json',sources);table(OUT/'source_index.csv',[{k:v for k,v in s.items() if k!='files_sha256'} for s in sources])
    dump(OUT/'metrics.json',list(metrics.values()));dump(OUT/'comparisons.json',comparisons)
    table(OUT/'results.csv',flat);dump(OUT/'results.json',flat);table(OUT/'stage_A.csv',stageA);table(OUT/'stage_B.csv',stageB)
    table(OUT/'comparisons.csv',comparisons,[k for k in comparisons[0] if k not in ('worst_ratio_case','worst_absolute_case')]);table(OUT/'paired_jobs.csv',pairs)
    dump(OUT/'worst_cases.json',[dict(comparison=c['comparison'],phase=c['phase'],scenario=c['scenario'],method=c['method'],baseline=c['baseline'],worst_ratio_case=c['worst_ratio_case'],worst_absolute_case=c['worst_absolute_case']) for c in comparisons])
    dump(OUT/'raw_integrity.json',dict(status='PASS',files_sha256=integrity,new_execution_jobs=sum(r.get('completed') or 0 for r in new),reused_execution_jobs=720,warning='Pair rows and reused rows are not new independent execution samples'))
    print('R2_READ_ONLY_ANALYSIS_PASS',flush=True)
if __name__=='__main__':main()
