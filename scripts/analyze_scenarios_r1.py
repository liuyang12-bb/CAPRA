"""Post-run raw-event analysis. No scheduler/allocator imports or simulated runs."""
from pathlib import Path
from collections import Counter,defaultdict
import csv,gzip,hashlib,itertools,json,math
import numpy as np
from capra.response import Responses
from capra.inputs import resolve_inputs
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runs/scenarios_r1/CAPRA_V2_SCENARIOS_R1'
def load(p):return json.loads(p.read_text(encoding='utf8'))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def table(p,rows):
    if not rows:return
    with p.open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
def near(a,b):assert abs(a-b)<1e-6,(a,b)
def distribution(xs):
    return dict(n=len(xs),mean=float(np.mean(xs)),median=float(np.median(xs)),p05=float(np.quantile(xs,.05)),p95=float(np.quantile(xs,.95)),min=min(xs),max=max(xs),positive=sum(x>1e-9 for x in xs),zero=sum(abs(x)<=1e-9 for x in xs),negative=sum(x<-1e-9 for x in xs)) if xs else dict(n=0)
def semantic(r):
    # All execution semantics, without timing/cache/path/scenario metadata.
    fields=('round','time','interval','method','plan','raw_sia_plan','lock_repaired_gpu_plan','current','locks','lock_remaining','started','allocations','node_usage','transitions','commit_predictions','post_commit_remaining','executions','completed','total')
    return {k:r[k] for k in fields}
def pool_ram(k,candidate,r,nodes,response):
    a=candidate['mapping_before'];target=a[k];n=nodes[target['node']];g=target['gpus']
    same=[j for j in a if a[j]['node']==target['node']]
    base={j:(r['locks'][j] if j in r['locks'] else dict(cpu=n['cpu']*a[j]['gpus']/n['gpus'],ram=n['ram']*a[j]['gpus']/n['gpus'])) for j in same}
    points={x*g for x in response.data['ram_axis']};points.add(base[k]['ram']);points.add(n['ram']-sum(base[j]['ram'] for j in same if j!=k))
    old=r['current'].get(k)
    if old and old['gpu_type']==target['gpu_type'] and old['gpus']==g and response.data['cpu_axis'][0]*g-1e-9<=old['cpu']<=min(n['cpu'],response.data['cpu_axis'][-1]*g)+1e-9 and response.data['ram_axis'][0]*g-1e-9<=old['ram']<=min(n['ram'],response.data['ram_axis'][-1]*g)+1e-9:points.add(old['ram'])
    return sorted(x for x in points if response.data['ram_axis'][0]*g-1e-9<=x<=min(n['ram'],response.data['ram_axis'][-1]*g)+1e-9)
def analyze_cell(directory):
    start=load(directory/'start.json');summary=load(directory/'summary.json');inputs=resolve_inputs(start)
    response=Responses(inputs['responses']);nodes={n['id']:n for n in load(inputs['cluster'])}
    rows=list(csv.DictReader(inputs['workload'].open(encoding='utf8',newline='')))
    app={r['name']:r['application'] for r in rows};arrival={r['name']:float(r['time']) for r in rows}
    stats={k:dict(waiting=0.,training=0.,recovery=0.,completion=None,progress=0.) for k in app}
    scenario_id=start.get('scenario_id') or 'original_'+Path(start['input']).stem
    cn=scenario_id.endswith(('_cn','_cm'))
    cls={k:(response.data['profiles'][v].get('sensitivity_class','original:'+v) if cn else 'original:'+v) for k,v in app.items()}
    weighted=Counter();app_train=Counter();app_gpu=Counter();class_train=Counter();class_gpu=Counter();app_cond=defaultdict(Counter)
    occupancy={nid:Counter() for nid in nodes};active=0;allrounds=0;selected=Counter();feasible=Counter();failures=Counter();transitions=Counter();pure=0
    score_delta=defaultdict(list);raw_delta=defaultdict(list);positive_r_raw=0;r_cost_only=0;selected_below_f_raw=0;decision=[];all_decision=[]
    funnel_rounds=Counter();funnel_train=Counter();pair_counts=Counter();opportunity_rounds=set();ram_gap_rounds=set();certificates=[];candidate_rows=[]
    semantic_hash=hashlib.sha256();active_jobs_train=0.;lock_train=0.
    roles_cache={}
    def roles(k,p):
        cachekey=(app[k],p['gpu_type'],p['gpus'])
        if cachekey not in roles_cache:
            n=next(n for n in nodes.values() if n['gpu_type']==p['gpu_type']);g=p['gpus'];cp=n['cpu']*g/n['gpus'];mp=n['ram']*g/n['gpus'];base=response.rho(app[k],g,cp,mp)
            roles_cache[cachekey]=dict(cpu_donor=any(c*g<cp-1e-7 and response.rho(app[k],g,c*g,mp)>=base-1e-9 for c in response.data['cpu_axis']),
                ram_donor=any(m*g<mp-1e-7 and response.rho(app[k],g,cp,m*g)>=base-1e-9 for m in response.data['ram_axis']),
                cpu_receiver=response.rho(app[k],g,n['cpu'],mp)>base+1e-9,
                ram_receiver=response.rho(app[k],g,cp,n['ram'])>base+1e-9)
        return roles_cache[cachekey]
    with gzip.open(directory/'events.jsonl.gz','rt',encoding='utf8') as f:
        for line in f:
            r=json.loads(line);allrounds+=1;all_decision.append(r['decision_seconds'])
            semantic_hash.update((json.dumps(semantic(r),sort_keys=True,separators=(',',':'))+'\n').encode('utf8'))
            for t in r['transitions']:
                transitions[t['kind']]+=1
                if t['kind']=='migration' and (t['old']['gpu_type'],t['old']['gpus'])==(t['new']['gpu_type'],t['new']['gpus']):pure+=1
            candidates={c['label']:c for c in r['selection']['candidates']}
            chosen=candidates[r['selection']['selected']]
            if r['plan']:
                active+=1;decision.append(r['decision_seconds']);selected[chosen['label']]+=1
                for label,c in candidates.items():
                    if c['feasible']:feasible[label]+=1
                    else:failures[label+':'+c['reason']]+=1
                fref=candidates.get('F',candidates.get('P'))
                fraw=sum(a['rho'] for a in fref['allocations'].values());fphi=fref['score']['phi']
                for label,c in candidates.items():
                    if c['feasible']:
                        d=c['score']['phi']-fphi;dr=sum(a['rho'] for a in c['allocations'].values())-fraw
                        score_delta[label].append(d);raw_delta[label].append(dr)
                        candidate_rows.append(dict(round=r['round'],label=label,selected=label==chosen['label'],phi=c['score']['phi'],phi_minus_F=d,sum_rho_minus_F=dr,total_delay=c['score']['total_delay']))
                        if label=='R':
                            positive_r_raw+=dr>1e-9;r_cost_only+=d>1e-9 and dr<=1e-9
                selected_below_f_raw+=sum(a['rho'] for a in chosen['allocations'].values())<fraw-1e-9
                # Nested pair funnel. Reweight each round by actual total job-training seconds.
                train_round=sum(e['training'] for e in r['executions']);flags=set();compatible=set();same_f=set();lockblocked=set();capacityblocked=set()
                for k,j in itertools.combinations(sorted(r['plan']),2):
                    if cls[k]==cls[j]:continue
                    flags.add('different_sensitivity_selected')
                    pk,pj=r['plan'][k],r['plan'][j]
                    rk,rj=roles(k,pk),roles(j,pj)
                    resources=[field for field in ('cpu','ram') if (rk[field+'_donor'] and rj[field+'_receiver']) or (rj[field+'_donor'] and rk[field+'_receiver'])]
                    for field in resources:flags.add(field+'_complement_selected')
                    if pk['gpu_type']!=pj['gpu_type']:continue
                    flags.add('same_gpu_type')
                    for field in resources:flags.add(field+'_complement_same_type')
                    ns=[n for n in nodes.values() if n['gpu_type']==pk['gpu_type']]
                    if pk['gpus']+pj['gpus']>max(n['gpus'] for n in ns):continue
                    flags.add('pair_gpu_sum_fits');compatible.add((k,j));pair_counts['|'.join(sorted((cls[k],cls[j])))]+=1
                    for field in resources:flags.add(field+'_complement_gpu_sum_fits')
                    if fref['allocations'][k]['node']==fref['allocations'][j]['node']:
                        flags.add('F_already_colocated');same_f.add((k,j))
                        for field in resources:flags.add(field+'_complement_F_colocated')
                    elif k in r['locks'] and j in r['locks']:
                        flags.add('both_locked_separate');lockblocked.add((k,j))
                        for field in resources:flags.add(field+'_complement_both_locked_separate')
                    # Fixed all third jobs; direct one-job moves only, no claims about swaps.
                    elif any(x in r['locks'] for x in (k,j)):
                        flags.add('one_or_more_locked')
                        for field in resources:flags.add(field+'_complement_one_or_more_locked')
                    if fref['allocations'][k]['node']!=fref['allocations'][j]['node']:
                        direct=[]
                        for moving,peer in ((k,j),(j,k)):
                            if moving in r['locks']:continue
                            dst=fref['allocations'][peer]['node'];n=nodes[dst]
                            occupied=sum(x['gpus'] for x in fref['allocations'].values() if x['node']==dst)
                            direct.append(occupied+r['plan'][moving]['gpus']<=n['gpus'])
                        if direct and not any(direct):
                            flags.add('direct_move_blocked_by_peer_node_gpu');capacityblocked.add((k,j))
                            for field in resources:flags.add(field+'_complement_direct_move_blocked_gpu')
                for flag in flags:funnel_rounds[flag]+=1;funnel_train[flag]+=train_round
                if compatible and compatible<=same_f: funnel_rounds['all_compatible_pairs_already_F']+=1;funnel_train['all_compatible_pairs_already_F']+=train_round
                active_jobs_train+=train_round
            for e in r['executions']:
                k=e['job'];s=stats[k];near(s['progress'],e['progress_before']);s['progress']=e['progress_after'];s['completion']=e['completion_time']
                for field in ('waiting','training','recovery'):s[field]+=e[field]
                a=e['allocation']
                if a:
                    duration=e['end']-e['start']
                    for field in ('gpus','cpu','ram'):occupancy[a['node']][field]+=a[field]*duration
                if not e['training']:continue
                near(sum(x['seconds'] for x in e['segments']),e['training'])
                n=nodes[a['node']];g=a['gpus'];cp=n['cpu']*g/n['gpus'];mp=n['ram']*g/n['gpus'];prop=response.rho(app[k],g,cp,mp)
                rho=response.rho(app[k],g,a['cpu'],a['ram']);near(a['rho'],rho)
                cd=rho-response.rho(app[k],g,cp,a['ram']);md=rho-response.rho(app[k],g,a['cpu'],mp)
                duration=e['training'];weighted['training']+=duration;weighted['rho']+=duration*rho;weighted['relative']+=duration*rho/prop
                weighted['above_prop']+=duration*(rho>prop+1e-9);weighted['cpu_difference']+=duration*cd;weighted['ram_difference']+=duration*md
                weighted['cpu_positive']+=duration*(cd>1e-9);weighted['ram_positive']+=duration*(md>1e-9)
                for role,present in roles(k,a).items():weighted[role+'_training']+=duration*present
                weighted['cpu_below_prop_no_loss_training']+=duration*(a['cpu']<cp-1e-7 and rho>=prop-1e-9)
                weighted['ram_below_prop_no_loss_training']+=duration*(a['ram']<mp-1e-7 and rho>=prop-1e-9)
                app_train[app[k]]+=duration;app_gpu[app[k]]+=duration*g;class_train[cls[k]]+=duration;class_gpu[cls[k]]+=duration*g
                app_cond[app[k]]['training']+=duration;app_cond[app[k]]['cpu_difference']+=duration*cd;app_cond[app[k]]['ram_difference']+=duration*md;app_cond[app[k]]['relative']+=duration*rho/prop
                if k in r['locks']:lock_train+=duration
                # Independent one-job slack certificates at decision-time capacity; no shared-gain sum.
                free_c=n['cpu']-r['node_usage'][n['id']][1];free_m=n['ram']-r['node_usage'][n['id']][2]
                cnew=min(response.data['cpu_axis'][-1]*g,a['cpu']+max(0,free_c));mnew=min(response.data['ram_axis'][-1]*g,a['ram']+max(0,free_m))
                rc=response.rho(app[k],g,cnew,a['ram']);rm=response.rho(app[k],g,a['cpu'],mnew);rjoint=response.rho(app[k],g,cnew,mnew)
                if rjoint>rho+1e-7:
                    assert r['node_usage'][n['id']][1]-a['cpu']+cnew<=n['cpu']+1e-7
                    assert r['node_usage'][n['id']][2]-a['ram']+mnew<=n['ram']+1e-7
                    assert cnew>=response.data['cpu_axis'][0]*g-1e-7 and mnew>=response.data['ram_axis'][0]*g-1e-7
                    assert rjoint>=prop-1e-7
                    locked=k in r['locks'];gap=False;pool=[]
                    if chosen['label']!='P' and not locked and rm>rho+1e-7:
                        pool=pool_ram(k,chosen,r,nodes,response)
                        gap=not any(x<=mnew+1e-7 and response.rho(app[k],g,a['cpu'],x)>rho+1e-7 for x in pool)
                    certificates.append(dict(round=r['round'],time=r['time'],job=k,application=app[k],node=n['id'],gpus=g,cpu=a['cpu'],ram=a['ram'],rho=rho,
                        free_cpu=free_c,free_ram=free_m,proposed_cpu=cnew,proposed_ram=mnew,rho_cpu_only=rc,rho_ram_only=rm,rho_joint=rjoint,
                        training_seconds=duration,locked_at_decision=locked,ram_candidate_gap=gap,ram_pool=pool,
                        scope='One target, all other tasks/positions fixed; certificates share slack, never sum gains'))
                    if not locked:opportunity_rounds.add(r['round']);weighted['slack_opportunity_training']+=duration
                    if gap:ram_gap_rounds.add(r['round']);weighted['ram_gap_training']+=duration
    completed=[k for k,s in stats.items() if s['completion'] is not None]
    for k in completed:near(stats[k]['completion']-arrival[k],sum(stats[k][x] for x in ('waiting','training','recovery')))
    per={r['job']:r for r in csv.DictReader((directory/'per_job.csv').open(encoding='utf8',newline=''))}
    for k,s in stats.items():
        for field in ('waiting','training','recovery','progress'):near(s[field],float(per[k][field]))
        if k in completed:near(s['completion'],float(per[k]['completion']))
    all_done=len(completed)==len(stats);jcts=[stats[k]['completion']-arrival[k] for k in completed]
    for field,value in [('mean_jct',np.mean(jcts)),('p50_jct',np.quantile(jcts,.5)),('p95_jct',np.quantile(jcts,.95)),('p99_jct',np.quantile(jcts,.99))]:
        if all_done:near(float(value),summary[field])
        else:assert summary[field] is None
    window=max(stats[k]['completion'] for k in completed)-min(arrival.values()) if all_done else None
    occ=[]
    for nid,seconds in occupancy.items():
        for field in ('gpus','cpu','ram'):
            occ.append(dict(node=nid,gpu_type=nodes[nid]['gpu_type'],resource=field,allocated_seconds=seconds[field],capacity=nodes[nid][field],window=window,allocated_fraction=seconds[field]/window/nodes[nid][field] if window else None,scope='Includes recovery occupancy, not hardware busy utilization'))
    for typ in sorted({n['gpu_type'] for n in nodes.values()}):
        for field in ('gpus','cpu','ram'):
            ids=[k for k,n in nodes.items() if n['gpu_type']==typ];secs=sum(occupancy[k][field] for k in ids);cap=sum(nodes[k][field] for k in ids)
            occ.append(dict(node='TYPE_TOTAL',gpu_type=typ,resource=field,allocated_seconds=secs,capacity=cap,window=window,allocated_fraction=secs/window/cap if window else None,scope='Includes recovery occupancy, not hardware busy utilization'))
    total=weighted['training'];training_metrics={k:weighted[k]/total for k in ('rho','relative','above_prop','cpu_difference','ram_difference','cpu_positive','ram_positive','slack_opportunity_training','ram_gap_training','cpu_donor_training','ram_donor_training','cpu_receiver_training','ram_receiver_training','cpu_below_prop_no_loss_training','ram_below_prop_no_loss_training')}
    metrics=dict(scenario=scenario_id,method=start['method'],raw_audit='PASS',completed=len(completed),total=len(stats),active_rounds=active,all_rounds=allrounds,
        training_metrics=training_metrics,application_training_share={k:v/total for k,v in app_train.items()},application_gpu_time_share={k:v/sum(app_gpu.values()) for k,v in app_gpu.items()},
        sensitivity_training_share={k:v/total for k,v in class_train.items()},sensitivity_gpu_time_share={k:v/sum(class_gpu.values()) for k,v in class_gpu.items()},
        application_conditionals={k:{field:v[field]/v['training'] for field in ('cpu_difference','ram_difference','relative')} for k,v in app_cond.items()},
        active_selected=dict(selected),active_feasible=dict(feasible),candidate_failures=dict(failures),phi_minus_F={k:distribution(v) for k,v in score_delta.items()},sum_rho_minus_F={k:distribution(v) for k,v in raw_delta.items()},
        R_raw_rho_above_F_rounds=positive_r_raw,R_phi_above_F_without_raw_rho_advantage_rounds=r_cost_only,selected_raw_rho_below_F_rounds=selected_below_f_raw,
        funnel_rounds=dict(funnel_rounds),funnel_training_fraction={k:v/active_jobs_train for k,v in funnel_train.items()},compatible_pair_round_occurrences=dict(pair_counts),
        opportunity_certificate_count=len(certificates),unlocked_slack_opportunity_rounds=len(opportunity_rounds),ram_candidate_gap_rounds=len(ram_gap_rounds),
        lock_training_fraction=lock_train/total,transitions=dict(transitions),pure_node_migrations=pure,actual_recovery_seconds=sum(s['recovery'] for s in stats.values()),
        decision_active=distribution(decision),decision_all_rounds=distribution(all_decision),semantic_sha256=semantic_hash.hexdigest(),
        opportunity_scope='Nested descriptive pair flags; training weighting uses all actual training in flagged rounds. Pair counts not unique jobs. Direct moves hold all third jobs fixed, no swap/global-optimality claim.')
    analysis=directory/'analysis_r1';analysis.mkdir(exist_ok=True)
    dump(analysis/'opportunity_metrics.json',metrics);dump(analysis/'slack_certificates.json',certificates)
    table(analysis/'occupancy.csv',occ);table(analysis/'candidate_deltas.csv',candidate_rows)
    return metrics,stats
def main():
    results=load(OUT/'results.json');analyses=[];stats={};integrity={}
    costs_by_scenario={}
    for row in results:
        if row.get('audit')!='PASS':continue
        directory=ROOT/row['output']
        start=load(directory/'start.json')
        assert start['version']==row['version']=='CAPRA_V2_SCENARIOS_R1' and start['scenario_id']==row['scenario']
        assert start['method']==row['method'] and not start['neutral'] and start['max_jobs'] is None
        assert start['interval']==60 and start['max_rounds']==6000 and start['horizon']==180
        for kind,key in (('workload','input'),('cluster','cluster'),('responses','responses')):
            assert start['inputs'][kind]['relative']==row[key]
            assert start['inputs'][kind]['sha256']==sha(ROOT/row[key])
        if row['scenario'] in costs_by_scenario:assert start['costs']==costs_by_scenario[row['scenario']]
        else:costs_by_scenario[row['scenario']]=start['costs']
        for p in directory.iterdir():
            if p.is_file():integrity[p.relative_to(ROOT).as_posix()]=sha(p)
        m,s=analyze_cell(directory);analyses.append(m);stats[(row['scenario'],row['method'])]=s
        print(json.dumps(dict(event='ANALYZED',scenario=row['scenario'],method=row['method'],metrics=m['training_metrics'],ram_gap_rounds=m['ram_candidate_gap_rounds'])),flush=True)
    for p,h in integrity.items():assert sha(ROOT/p)==h,('ANALYSIS_MODIFIED_RAW',p)
    cn=next((r for r in results if r['scenario']=='w2_dense_cn' and r['method']=='SIA-P' and r['status']=='ALL_COMPLETE'),None)
    cm=next((r for r in results if r['scenario']=='w2_dense_cm' and r['method']=='SIA-P' and r['status']=='ALL_COMPLETE'),None)
    control=dict(status='NOT_AVAILABLE')
    if cn and cm:
        a=ROOT/cn['output'];b=ROOT/cm['output'];sa=load(a/'start.json');sb=load(b/'start.json')
        for key in ('input_sha256','cluster_sha256','costs'):assert sa[key]==sb[key],('CONTROL_METADATA',key)
        assert stats[('w2_dense_cn','SIA-P')]==stats[('w2_dense_cm','SIA-P')],'CONTROL_PER_JOB'
        ma=next(x for x in analyses if x['scenario']=='w2_dense_cn' and x['method']=='SIA-P');mb=next(x for x in analyses if x['scenario']=='w2_dense_cm' and x['method']=='SIA-P')
        assert ma['semantic_sha256']==mb['semantic_sha256'],'CONTROL_EXECUTION_TRACE'
        control=dict(status='PASS',jobs=80,rounds=ma['all_rounds'],input_sha256=sa['input_sha256'],cluster_sha256=sa['cluster_sha256'],semantic_sha256=ma['semantic_sha256'],costs_equal=True,per_job_equal=True,scope='GPU plans, complete allocations, batches, recovery state, progress and execution segments; excludes wall/cache/path/scenario metadata')
    dump(OUT/'cn_cm_siap_control.json',control);dump(OUT/'opportunity_summary.json',analyses)
    legacy=[]
    for w in (2,6):
        for method in ('SIA-P','CAPRA-Fixed','CAPRA'):
            directory=ROOT/f'runs/scenarios_r1/development/prior_replay/w{w}/{method}'
            m,_=analyze_cell(directory);legacy.append(dict(workload=w,**m))
    dump(OUT/'original_v2_opportunity_reference.json',legacy)
    paired=[]
    for scenario in dict.fromkeys(r['scenario'] for r in results):
        if not all((scenario,m) in stats for m in ('SIA-P','CAPRA-Fixed','CAPRA')):continue
        for k in stats[(scenario,'SIA-P')]:
            r=dict(scenario=scenario,job=k)
            for method,tag in (('SIA-P','sia'),('CAPRA-Fixed','fixed'),('CAPRA','capra')):
                x=stats[(scenario,method)][k];r[tag+'_completion']=x['completion']
                for field in ('waiting','training','recovery'):r[tag+'_'+field]=x[field]
                r[tag+'_jct']=sum(x[field] for field in ('waiting','training','recovery')) if x['completion'] is not None else None
            for base in ('sia','fixed'):
                r['capra_minus_'+base]=r['capra_jct']-r[base+'_jct'] if r['capra_jct'] is not None and r[base+'_jct'] is not None else None
            paired.append(r)
    table(OUT/'paired_jobs.csv',paired)
    dump(OUT/'post_analysis_integrity.json',dict(status='PASS',raw_files_unchanged=len(integrity),files_sha256=integrity))
    print('RAW_ANALYSIS_PASS',flush=True)
if __name__=='__main__':main()
