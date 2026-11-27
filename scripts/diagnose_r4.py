"""Budgeted read-only funnels, eight preregistered small-state reviews, real cases."""
from collections import Counter
import csv,gzip,json,itertools,time,hashlib
from r4_utils import *
from opportunity_r4 import funnel_round,STAGES,best_reference,legal_vector
OUT=RUN/'analysis'
def table(p,rows):
    if not rows:return
    with Path(p).open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
def raw(d):
    with gzip.open(d/'events.jsonl.gz','rt',encoding='utf8') as f:return [json.loads(x) for x in f]
def context(d):
    s=load(d/'start.json');nodes={n['id']:n for n in load(ROOT/s['inputs']['cluster']['relative'])};apps={x['name']:x['application'] for x in csv.DictReader((ROOT/s['inputs']['workload']['relative']).open(encoding='utf8'))}
    from capra.response import Responses
    return s,nodes,apps,Responses(ROOT/s['inputs']['responses']['relative'])
def bounded_review(source,r):
    from capra.contracts import Node,JobGpuPlan,Allocation,serialized,validate
    from capra.response_v2 import V2Responses
    from capra.placement_r3 import create_placement
    from capra.audit_r4 import score as independent_score
    d=ROOT/source['output'];s,nodes,apps,response=context(d);p=r['plan'];locked=r['locks'];todo=sorted(set(p)-set(locked))
    assert len(p)<=6 and len(todo)<=4
    options=[sorted(n for n,x in nodes.items() if x['gpu_type']==p[k]['gpu_type']) for k in todo]
    assert all(len(x)<=2 for x in options);bound=1
    for x in options:bound*=len(x)
    assert bound<=16
    args=({k:JobGpuPlan(**v) for k,v in p.items()},[Node(**n) for n in nodes.values()],apps,V2Responses(ROOT/s['inputs']['responses']['relative']),{k:Allocation(**v) for k,v in r['current'].items()},{k:Allocation(**v) for k,v in locked.items()},r['lock_remaining'],s['costs'],set(r['started']))
    solver=create_placement(*args,method='CAPRA',allocator_mode='ram_slack_v1');rows=[];best=None;attempts=0
    costs={a:next(iter(v.values())) for a,v in s['costs'].items()}
    for ids in itertools.product(*options):
        check_budget();attempts+=1;layout={k:a['node'] for k,a in locked.items()};layout.update(dict(zip(todo,ids)))
        baseline,reasons=legal_vector(p,layout,nodes,locked,response,apps)
        if baseline is None:rows.append(dict(layout=layout,feasible=False,reasons=reasons));continue
        allocation,meta=solver.allocator.layout(layout);c=solver.finish('DIAGNOSTIC_ONLY',allocation,meta)
        validate(args[0],c['allocations'],args[1],args[5]);a=serialized(c['allocations']);ind=independent_score(a,r['current'],locked,r['lock_remaining'],apps,costs,set(r['started']))
        for k in ('phi','total_delay','total_new_cost','changes'):assert abs(c['score'][k]-ind[k])<=1e-7
        for k,x in a.items():assert abs(x['rho']-response.rho(apps[k],x['gpus'],x['cpu'],x['ram']))<=1e-7
        rec=dict(layout=layout,stable_allocations=a,feasible=True,phi=c['score']['phi'],sum_rho=sum(x['rho'] for x in a.values()),total_delay=c['score']['total_delay'],new_cost=c['score']['total_new_cost'],changes=c['score']['changes'],allocator_meta=meta)
        rows.append(rec)
        if best is None or rec['phi']>best['phi']+1e-9 or (abs(rec['phi']-best['phi'])<=1e-9 and (rec['total_delay'],rec['changes'])<(best['total_delay'],best['changes'])):best=rec
    assert attempts==bound and best is not None
    reference,_=best_reference(r['selection']['candidates']);valid=[c for c in r['selection']['candidates'] if c['feasible']];recorded_best=max(c['score']['phi'] for c in valid)
    rcan=next(c for c in r['selection']['candidates'] if c['label']=='R')
    original_layouts=[tuple((k,x['node']) for k,x in sorted(c['allocations'].items())) for c in valid]
    b_layout=tuple((k,x['node']) for k,x in sorted(best['stable_allocations'].items()))
    return dict(source=source['output'],scenario=source['scenario'],round=r['round'],time=r['time'],status='PASS',jobs=len(p),unlocked=len(todo),layout_bound=bound,attempted_layouts=attempts,feasible_layouts=sum(x['feasible'] for x in rows),layouts=rows,best=best,FK_reference_phi=reference['score']['phi'],recorded_best_phi=recorded_best,R_phi=rcan['score']['phi'] if rcan['feasible'] else None,best_over_FK_phi=best['phi']-reference['score']['phi'],best_over_recorded_phi=best['phi']-recorded_best,positive_net_layout_missed_by_recorded_candidates=best['phi']>recorded_best+1e-9,best_layout_not_in_recorded_candidates=b_layout not in original_layouts,allocator_statistics=solver.allocator.stats(),scope='At most16 whole layouts in preregistered small fixed-GPU state; original finite node allocator and score, not global quota/JCT optimum')
def cases_for(source,rows,baseline_directory,historical=False):
    d=ROOT/source['output'];base=Path(baseline_directory)
    if not (base/'per_job.csv').exists():return []
    full={x['job']:x for x in csv.DictReader((d/'per_job.csv').open(encoding='utf8'))};other={x['job']:x for x in csv.DictReader((base/'per_job.csv').open(encoding='utf8'))};changed={}
    for r in rows:
        if r['selection']['selected']!='R':continue
        for t in r['transitions']:
            if t['new'] is not None and t['job'] in full:changed.setdefault(t['job'],[]).append(r)
    eligible=[k for k in changed if full[k]['jct'] and other[k]['jct']];slow=[k for k in eligible if float(full[k]['jct'])>float(other[k]['jct'])+1e-7];fast=[k for k in eligible if float(full[k]['jct'])<float(other[k]['jct'])-1e-7]
    picks=[]
    if slow:picks.append(('worst_R_involved_relative_degradation',max(slow,key=lambda k:float(full[k]['jct'])/float(other[k]['jct']))))
    if fast:picks.append(('best_R_involved_absolute_improvement',min(fast,key=lambda k:float(full[k]['jct'])-float(other[k]['jct']))))
    out=[]
    for label,k in picks:
        start=changed[k][0];selected=next(c for c in start['selection']['candidates'] if c['label']=='R');ref,_=best_reference(start['selection']['candidates'])
        timeline=[]
        for r in rows:
            if r['round']<start['round']:continue
            e=next((e for e in r['executions'] if e['job']==k),None)
            if e:timeline.append(dict(round=r['round'],time=r['time'],selected=r['selection']['selected'],allocation=e['allocation'],batch=e['batch_after'],progress_before=e['progress_before'],progress_after=e['progress_after'],waiting=e['waiting'],training=e['training'],recovery=e['recovery'],rescale_remaining=e['rescale_remaining'],completion=e['completion_time'],transitions=[x for x in r['transitions'] if x['job']==k]))
        # The row is a real dynamic paired outcome, never attributed solely to this R action.
        out.append(dict(case=label,result_origin='HISTORICAL_REFERENCE' if historical else 'NEW_EXECUTION',scenario=source['scenario'],source=source['output'],source_events_sha256=sha(d/'events.jsonl.gz'),baseline=str(base.relative_to(ROOT)),baseline_events_sha256=sha(base/'events.jsonl.gz'),job_id=k,R_round=start['round'],R_time=start['time'],before=start['current'].get(k),R_allocation=selected['allocations'].get(k),FK_reference_allocation=ref['allocations'].get(k),predicted_R=selected['score']['jobs'].get(k),predicted_reference=ref['score']['jobs'].get(k),R_phi=selected['score']['phi'],FK_phi=ref['score']['phi'],actual_full_ledger={x:float(full[k][x]) for x in ('jct','waiting','training','recovery')},actual_baseline_ledger={x:float(other[k][x]) for x in ('jct','waiting','training','recovery')},delta_jct=float(full[k]['jct'])-float(other[k]['jct']),jct_ratio=float(full[k]['jct'])/float(other[k]['jct']),subsequent_execution_and_reconfiguration=timeline,warning='Whole dynamic trajectories diverge; ledger delta is not a strict causal effect of one R action'))
    if not picks:out.append(dict(case='NO_ELIGIBLE_R_INVOLVED_PAIRED_JOB',scenario=source['scenario'],source=source['output'],R_selected_rounds=sum(r['selection']['selected']=='R' for r in rows)))
    return out
def main():
    began=time.perf_counter();check_budget();OUT.mkdir(exist_ok=True);physical=load(RUN/'results.json');aggregates=[];cases=[];samples=[];sample_rules=[];integrity={}
    for source in physical:
        if source['state']!='COMPLETE_PASS':continue
        check_budget();d=ROOT/source['output'];s,nodes,apps,response=context(d);rows=raw(d);cache={};counts=Counter();tags=Counter();denom=sum(bool(r['plan']) for r in rows);selected=0;out=OUT/'cells'/source['scenario']/source['method'];out.mkdir(parents=True,exist_ok=True);observed=[]
        for name in ('start.json','events.jsonl.gz','summary.json','per_job.csv'):integrity[(d/name).relative_to(ROOT).as_posix()]=sha(d/name)
        with gzip.open(out/'opportunity_rounds.jsonl.gz','wt',encoding='utf8') as f:
            for r in rows:
                check_budget();v=funnel_round(r,nodes,response,apps,cache);observed.append(v)
                for k,x in v['stages'].items():counts[k]+=x
                if v['denominator_nonempty']:tags.update(v['nonexclusive_tags'])
                selected+=v['R_selected'];f.write(json.dumps(v,ensure_ascii=False)+'\n')
        assert counts['A']==denom and all(counts[b]<=counts[a] for a,b in zip(STAGES,list(STAGES)[1:]))
        for k,definition in STAGES.items():aggregates.append(dict(scenario=source['scenario'],method=source['method'],stage=k,definition=definition,numerator=counts[k],denominator_nonempty_rounds=denom,fraction=counts[k]/denom if denom else None,total_R_selected=selected,result_origin='NEW_EXECUTION'))
        dump(out/'opportunity_summary.json',dict(denominator_nonempty_rounds=denom,strict_nested_counts=dict(counts),nonexclusive_tag_round_counts=dict(tags),R_selected_all=selected,scope='Strict new-colocation sufficient-certificate funnel; protocol-not-generated is not an algorithm bug'))
        if source['method']=='CAPRA':
            eligible=[(r,v) for r,v in zip(rows,observed) if 0<len(r['plan'])<=6 and len(set(r['plan'])-set(r['locks']))<=4]
            selected_states={}
            for rule,predicate in [('first_E_uncovered_or_no_gross',lambda r,v:v['stages']['E'] and (not v['stages']['F'] or not v['stages']['G'])),('first_R_selected_small',lambda r,v:v['R_selected'])]:
                hit=next(((r,v) for r,v in eligible if predicate(r,v)),None)
                sample_rules.append(dict(scenario=source['scenario'],rule=rule,round=None if hit is None else hit[0]['round']))
                if hit:selected_states.setdefault(hit[0]['round'],dict(source=source,event=hit[0],rules=[]))['rules'].append(rule)
            samples.extend(selected_states.values());cases+=cases_for(source,rows,d.parent/'CAPRA-FK')
        print(json.dumps(dict(event='FUNNEL_READY',scenario=source['scenario'],method=source['method'],N=denom,stages=dict(counts))),flush=True)
    assert len(samples)<=8
    registration=dict(status='PREREGISTERED_RULE_APPLIED_BEFORE_ENUMERATION',max_states=8,max_layouts_per_state=16,max_total_layouts=128,rules=sample_rules,states=[dict(source=x['source']['output'],scenario=x['source']['scenario'],round=x['event']['round'],rules=x['rules'],event_sha256=hashlib.sha256(json.dumps(x['event'],sort_keys=True).encode()).hexdigest()) for x in samples])
    dump(OUT/'bounded_diagnostic_preregistration.json',registration)
    reviews=[]
    for x in samples:
        check_budget();review=bounded_review(x['source'],x['event']);review['selection_rules']=x['rules'];reviews.append(review)
    assert sum(x['attempted_layouts'] for x in reviews)<=128
    dump(OUT/'bounded_layout_reviews.json',reviews)
    # Two existing historical comparisons, exact raw sources and fixed criteria, no simulation.
    history=[dict(scenario='R2_w2_dense_cm_positive',output='runs/ablation_ram_r2/CAPRA_V2_RAM_R2/w2_dense_cm/CAPRA'),dict(scenario='R3_saturn8_cm_negative',output='runs/smart_holdout_r3/CAPRA_V2_HOLDOUT_R3/saturn8_supported80_cm/CAPRA')]
    histreps=[]
    for source in history:
        check_budget();d=ROOT/source['output'];rows=raw(d);s,nodes,apps,response=context(d)
        for name in ('start.json','events.jsonl.gz','summary.json','per_job.csv'):integrity[(d/name).relative_to(ROOT).as_posix()]=sha(d/name)
        hit=next((r for r in rows if r['selection']['selected']=='R'),None)
        histreps.append(dict(source=source,source_events_sha256=sha(d/'events.jsonl.gz'),first_R_round=None if hit is None else hit['round'],first_R_event=hit,warning='Historical explanation only, not new execution'))
        cases+=cases_for(source,rows,d.parent/'CAPRA-FK',historical=True)
    for p,h in integrity.items():assert sha(ROOT/p)==h
    table(OUT/'opportunity_funnel.csv',aggregates);dump(OUT/'opportunity_cases.json',cases);dump(OUT/'historical_representative_rounds.json',histreps)
    dump(OUT/'diagnostic_raw_integrity.json',dict(status='PASS',files_sha256=integrity))
    dump(OUT/'diagnosis_receipt.json',dict(status='PASS',wall_seconds=time.perf_counter()-began,funnel_cells=len(aggregates)//9,small_states=len(reviews),enumerated_layouts=sum(x['attempted_layouts'] for x in reviews),missed_positive_net_states=sum(x['positive_net_layout_missed_by_recorded_candidates'] for x in reviews),cases=len(cases),Job_step_calls=0,GPU_MIP_calls=0,no_global_JCT_optimum_claim=True))
    print('R4_BOUNDED_DIAGNOSIS_PASS',flush=True)
if __name__=='__main__':main()
