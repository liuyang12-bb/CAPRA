"""Independent read-only event/accounting analysis; all writes under R2 analysis."""
from collections import Counter,defaultdict
import csv,gzip,math
import numpy as np
from r3_utils import *
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

def extras(source):
    import itertools
    d=ROOT/source['output'];start=load(d/'start.json');paths=resolve_inputs(start)
    nodes={n['id']:n for n in load(paths['cluster'])};response=Responses(ROOT/source['target_responses'] if source.get('target_responses') else paths['responses'])
    apps={r['name']:r['application'] for r in csv.DictReader(paths['workload'].open(encoding='utf8',newline=''))}
    counts=Counter();funnel=Counter();funnel_train=Counter();app_training=Counter();app_gpu=Counter();smart_seconds=[];repair_jobs=Counter();timeline=[];rolecache={}
    def roles(k,p):
        ck=(apps[k],p['gpu_type'],p['gpus'])
        if ck not in rolecache:
            n=next(n for n in nodes.values() if n['gpu_type']==p['gpu_type']);g=p['gpus'];cp=n['cpu']*g/n['gpus'];mp=n['ram']*g/n['gpus'];base=response.rho(apps[k],g,cp,mp)
            rolecache[ck]={f+'_donor':any(z*g<v-1e-7 and response.rho(apps[k],g,z*g if f=='cpu' else cp,z*g if f=='ram' else mp)>=base-1e-9 for z in response.data[f+'_axis']) for f,v in [('cpu',cp),('ram',mp)]}
            rolecache[ck].update(cpu_receiver=response.rho(apps[k],g,n['cpu'],mp)>base+1e-9,ram_receiver=response.rho(apps[k],g,cp,n['ram'])>base+1e-9)
        return rolecache[ck]
    with gzip.open(d/'events.jsonl.gz','rt',encoding='utf8') as f:
        for line in f:
            r=__import__('json').loads(line);counts['all_rounds']+=1
            if r['plan']:counts['active_rounds']+=1
            train=sum(e['training'] for e in r['executions']);flags=set();ref=r['selection']['candidates'][0]['allocations']
            for a,b in itertools.combinations(sorted(r['plan']),2):
                if apps[a]==apps[b]:continue
                flags.add('different_application_selected');pa,pb=r['plan'][a],r['plan'][b];ra,rb=roles(a,pa),roles(b,pb)
                resources=[f for f in ('cpu','ram') if (ra[f+'_donor'] and rb[f+'_receiver']) or (rb[f+'_donor'] and ra[f+'_receiver'])]
                for f in resources:flags.add(f+'_complement_selected')
                if pa['gpu_type']!=pb['gpu_type']:continue
                flags.add('same_gpu_type')
                for f in resources:flags.add(f+'_complement_same_type')
                if pa['gpus']+pb['gpus']>max(n['gpus'] for n in nodes.values() if n['gpu_type']==pa['gpu_type']):continue
                flags.add('pair_gpu_sum_fits')
                for f in resources:flags.add(f+'_complement_gpu_sum_fits')
                if ref[a]['node']==ref[b]['node']:
                    flags.add('reference_already_colocated')
                    for f in resources:flags.add(f+'_complement_reference_colocated')
                elif a in r['locks'] and b in r['locks']:flags.add('both_locked_separate')
                elif a in r['locks'] or b in r['locks']:flags.add('one_or_more_locked')
                if ref[a]['node']!=ref[b]['node']:
                    direct=[]
                    for moving,peer in ((a,b),(b,a)):
                        if moving in r['locks']:continue
                        dst=ref[peer]['node'];use=sum(x['gpus'] for x in ref.values() if x['node']==dst)
                        direct.append(use+r['plan'][moving]['gpus']<=nodes[dst]['gpus'])
                    if direct and not any(direct):flags.add('direct_move_blocked_by_peer_gpu')
            for flag in flags:funnel[flag]+=1;funnel_train[flag]+=train
            for e in r['executions']:
                app_training[apps[e['job']]]+=e['training']
                if e['allocation']:app_gpu[apps[e['job']]]+=e['training']*e['allocation']['gpus']
            m=r['gpu_stage']
            if 'smart_records' not in m:continue
            if r['plan']:smart_seconds.append(m['smart_seconds'])
            evicted=[];kept=[];replaced=[]
            for c in m['smart_records']:
                kept+=c['retained'];evicted+=c['evicted'];replaced+=c['replaced']
                counts['raw_smart_cluster_calls']+=1
            counts['raw_retained_job_rounds']+=len(kept);counts['raw_evicted_job_events']+=len(evicted);counts['raw_replaced_job_rounds']+=len(replaced)
            if m['repairs']:
                counts['shared_witness_repair_rounds']+=1
                changed=[k for k,p in r['raw_sia_plan'].items() if p['node']!=r['lock_repaired_gpu_plan'][k]['node']]
                counts['shared_witness_changed_job_rounds']+=len(changed);repair_jobs.update(changed)
            else:changed=[]
            timeline.append(dict(round=r['round'],time=r['time'],retained=kept,evicted=evicted,replaced=replaced,physical_repair=bool(m['repairs']),repair_changed_jobs=changed,identity_swap_groups=sum(x['choice']=='swap' for x in r['reference']['mapping']['groups']),actual_jobs=len(r['allocations'])))
    total=sum(app_training.values());gpu=sum(app_gpu.values())
    result=dict(counts=dict(counts),smart_timing=dist(smart_seconds),repair_affected_jobs=dict(repair_jobs),repair_fraction_active=counts['shared_witness_repair_rounds']/counts['active_rounds'] if counts['active_rounds'] else None,opportunity_rounds=dict(funnel),opportunity_training_share={k:v/total for k,v in funnel_train.items()} if total else {},application_training_share={k:v/total for k,v in app_training.items()} if total else {},application_training_gpu_seconds_share={k:v/gpu for k,v in app_gpu.items()} if gpu else {},scope='Nested descriptive co-selection/type/packing/lock/reference flags, not independent causal contributions. Pair flags use app resource donor/receiver properties; all third tasks fixed for direct moves.')
    out=OUT/'cells'/source['id'];dump(out/'smart_and_opportunities.json',result);dump(out/'smart_timeline.json',timeline)
    return result

def main():
    import copy,hashlib
    OUT.mkdir(exist_ok=True);began=time.perf_counter();sources=[]
    freeze=load(RUN/'freeze_receipt.json') if (RUN/'freeze_receipt.json').exists() else None
    physical=load(RUN/'results.json') if (RUN/'results.json').exists() else []
    for r in physical:
        if r['status']=='ALL_COMPLETE' and r.get('audit')=='PASS':
            sources.append(dict(id=f'{r["phase"]}/{r["scenario"]}/{r["method"]}',phase=r['phase'],scenario=r['scenario'],profile=r['profile'],workload_id=r['workload_id'],method=r['method'],allocator_mode=r['allocator_mode'],phase_version=r['phase_version'],reused=False,executed=True,result_origin='NEW_EXECUTION',source_commit=None,base_commit=BASE,source_snapshot_sha256=r['source_snapshot_sha256'],output=r['output'],physical_index=r['index'],timing_scope='Measured current physical execution'))
    # Old A background: preserve real source version and legacy/repair labels.
    old=load(ROOT/'runs/ablation_ram_r2/analysis/source_index.json')
    for x in old:
        if x['scenario'] in ('w2_dense_original','w6_dense_original') and x['method'] in ('SIA-P','SIA-P-K','CAPRA-FK','CAPRA'):
            if x['method']=='CAPRA' and x['phase']!='R1':continue
            if x['method'] in ('SIA-P-K','CAPRA-FK') and x['phase']!='A':continue
        elif x['scenario']=='w2_dense_cm':
            if x['method']=='SIA-P' and x['phase']=='R1':pass
            elif x['method']=='SIA-P-K' and x['phase']=='A':pass
            elif x['method'] in ('CAPRA-Fixed','CAPRA-FK','CAPRA') and x['phase']=='B':pass
            else:continue
        else:continue
        y=dict(x,id='HISTORY/'+x['id'],phase='A',historical_phase=x['phase'],profile='CM' if x['scenario'].endswith('_cm') else 'original',workload_id='w2_dense' if x['scenario'].startswith('w2') else 'w6_dense',reused=True,executed=False,result_origin='HISTORICAL_REFERENCE',timing_scope='Historical source observed; missing component fields unavailable')
        # Physical source commit is its archived source_index commit, not relabelled as R3.
        y['base_containing_evidence']=BASE;sources.append(y)
    sources_before_alias=list(sources);aliases=[]
    if freeze and (RUN/'smart_control_certificate.json').exists():
        control=load(RUN/'smart_control_certificate.json');assert control['status']=='PASS' and control['strict']
        for reg in load(RUN/'logical_reuse_registration.json'):
            hits=[x for x in sources if x.get('physical_index')==reg['source_physical_index']]
            if not hits:continue
            src=hits[0];d=ROOT/src['output'];s=load(d/'summary.json');assert s['completed']==s['total']==80 and s['r3_raw_audit']=='PASS'
            rawhash=sha(d/'events.jsonl.gz');inp=load(d/'start.json')['inputs'];assert src['method'] in ('SIA-SMART-P','SIA-P-K')
            assert s['allocator_mode']=='none' and s['training_weighted_rho']==1.
            cert=dict(status='PASS',registration=reg,static_certificate_sha256=sha(DEV/'equivalence_static_certificate.json'),proportional_points_sha256=sha(DEV/'proportional_points.json'),R2_PK_control_sha256=sha(DEV/'r2_pk_control.json'),A_smart_control_sha256=sha(RUN/'smart_control_certificate.json'),source_run_id=src['id'],source_path=src['output'],source_input_hash=inp['workload']['sha256'],source_events_hash=rawhash,source_completed=80,source_total=80,source_audit_sha256=sha(d/'r3_audit.json'),source_profile='original',source_profile_sha256=inp['responses']['sha256'],target_profile='CM',target_profile_sha256=reg['target_profile_sha256'],executed=False,result_origin='EQUIVALENCE_REUSED')
            cp=OUT/'equivalence'/f'alias_{reg["index"]}.json';dump(cp,cert)
            a=dict(src,id=f'B/{reg["scenario"]}/{reg["method"]}',scenario=reg['scenario'],profile='CM',physical_index=None,logical_index=reg['index'],executed=False,reused=True,result_origin='EQUIVALENCE_REUSED',target_responses='data/scenarios_r1/responses_cm.json',equivalence_certificate_sha256=sha(cp),source_run_id=src['id'],source_path=src['output'],source_input_hash=cert['source_input_hash'],source_events_hash=rawhash,source_profile='original',source_profile_sha256=cert['source_profile_sha256'],target_profile='CM',target_profile_sha256=cert['target_profile_sha256'],timing_scope='Source original observed/reused; no CM timing measurement')
            sources.append(a);aliases.append(a)
    integrity={};metrics={};stats={};flat=[]
    for source in sources:
        d=ROOT/source['output'];source['files_sha256']={n:sha(d/n) for n in ('start.json','events.jsonl.gz','per_job.csv','summary.json','node_resources.csv')}
        for name,h in source['files_sha256'].items():integrity[(d/name).relative_to(ROOT).as_posix()]=h
        x,s=read_cell(source);x['extra']=extras(source)
        if (d/'process.json').exists():x['summary']['wall_seconds']=load(d/'process.json')['process_wall_seconds'];x['summary']['wall_scope']='source owned process including imports/audit'
        x['timing_scope']=source['timing_scope'];metrics[source['id']]=x;stats[source['id']]=s
        flat.append(dict(id=source['id'],phase=source['phase'],scenario=source['scenario'],profile=source['profile'],method=source['method'],allocator_mode=source['allocator_mode'],result_origin=source['result_origin'],executed=source['executed'],source_path=source['output'],timing_scope=source['timing_scope'],**{k:x['summary'].get(k) for k in ('status','completed','total','censored','mean_jct','p50_jct','p95_jct','p99_jct','makespan','mean_waiting','mean_training','mean_recovery','decision_median','decision_p95','decision_max','wall_seconds')},decision_gt5_count=(x['timing']['decision'] or {}).get('gt5_count',0)))
        print(__import__('json').dumps(dict(event='RAW_ANALYZED',id=source['id'],mean=x['summary']['mean_jct'],residual_ram_rounds=x['residual_ram_rounds'])),flush=True)
    comparisons=[];pairs=[]
    def add(label,phase,scenario,ida,idb):
        if ida not in metrics or idb not in metrics:return
        a,b=metrics[ida],metrics[idb]
        if a['summary']['completed']!=80 or b['summary']['completed']!=80:return
        c,p=compare(label,phase,scenario,a['source']['method'],b['source']['method'],a,b,stats[ida],stats[idb]);comparisons.append(c);pairs.extend(p)
    for scenario in ('w2_dense_original','w2_dense_cm','w6_dense_original'):
        sm=f'A/{scenario}/SIA-SMART-P'
        available={x['method']:x['id'] for x in sources if x['scenario']==scenario and x['result_origin']=='HISTORICAL_REFERENCE'}
        for method in ('SIA-P','SIA-P-K'):
            if method in available:add('smart_vs_'+method,'A',scenario,sm,available[method])
        for method in ('CAPRA-FK','CAPRA'):
            if method in available:add(method+'_vs_smart_historical_version','A',scenario,available[method],sm)
    for work in ('saturn7_supported80','saturn8_supported80'):
        for profile in ('original','cm'):
            scenario=work+'_'+profile
            for a,b in [('CAPRA','SIA-SMART-P'),('CAPRA-FK','SIA-SMART-P'),('CAPRA-FK','SIA-P-K'),('CAPRA','SIA-P-K'),('CAPRA','CAPRA-FK'),('SIA-SMART-P','SIA-P-K')]:
                add(a+'/'+b,'B',scenario,f'B/{scenario}/{a}',f'B/{scenario}/{b}')
    for p,h in integrity.items():assert sha(ROOT/p)==h,('RAW_MODIFIED',p)
    dump(OUT/'source_index.json',sources);table(OUT/'source_index.csv',[{k:v for k,v in x.items() if k!='files_sha256'} for x in sources],sorted({k for x in sources for k in x if k!='files_sha256'}))
    dump(OUT/'metrics.json',list(metrics.values()));dump(OUT/'results.json',flat);table(OUT/'results.csv',flat)
    dump(OUT/'comparisons.json',comparisons);table(OUT/'comparisons.csv',comparisons,[k for k in comparisons[0] if k not in ('worst_ratio_case','worst_absolute_case')] if comparisons else [])
    table(OUT/'paired_jobs.csv',pairs);dump(OUT/'worst_cases.json',[{k:c[k] for k in ('comparison','phase','scenario','method','baseline','worst_ratio_case','worst_absolute_case')} for c in comparisons])
    dump(RUN/'logical_reuse_results.json',aliases)
    dump(OUT/'raw_integrity.json',dict(status='PASS',files_sha256=integrity,new_physical_completed=sum(r.get('completed') or 0 for r in physical if r['status']=='ALL_COMPLETE'),logical_reused=len(aliases),independent_workloads=2,warning='Same Saturn source family, two holdout traces. Derived profiles and aliases are not independent workloads/executions.'))
    dump(OUT/'analysis_receipt.json',dict(status='PASS',wall_seconds=time.perf_counter()-began,physical_completed=sum(r['status']=='ALL_COMPLETE' for r in physical),logical_reused=len(aliases),historical_rows=sum(s['result_origin']=='HISTORICAL_REFERENCE' for s in sources),comparisons=len(comparisons),simulator_calls=0))
    print('R3_READ_ONLY_ANALYSIS_PASS',flush=True)
if __name__=='__main__':main()
