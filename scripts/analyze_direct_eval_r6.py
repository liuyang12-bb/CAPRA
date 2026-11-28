"""Read sealed logs only: complete paired JCT and exact R-L score decomposition."""
from pathlib import Path
from collections import Counter,defaultdict
import csv,gzip,json,sys,time,math
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from capra.protocol_direct_eval_r6 import RUN,BASE,R4,VERSION,EPS,PAIR_EPS,CAP_EPS,load,dump,sha

def table(path,rows,fields=None):
    with Path(path).open('w',encoding='utf8',newline='') as f:
        names=fields or (list(rows[0]) if rows else ['status']);w=csv.DictWriter(f,names,extrasaction='ignore');w.writeheader();w.writerows(rows)
def events(path):
    with gzip.open(path,'rt',encoding='utf8') as f:
        for line in f:yield json.loads(line)
def same_alloc(a,b):
    if set(a)!=set(b):return False
    return all(all((abs(v-b[k][f])<=CAP_EPS if isinstance(v,(int,float)) else v==b[k][f]) for f,v in x.items()) for k,x in a.items())
def score_parts(candidate):
    r=sum(x['rho'] for x in candidate['allocations'].values());loss=sum(x['rho']*min(candidate['score']['jobs'][k]['delay']/180.,1.) for k,x in candidate['allocations'].items());phi=candidate['score']['phi']
    assert abs(phi-(r-loss))<=1e-7
    return r,loss,phi
def read_source(spec):
    d=ROOT/spec['output'];summary=load(d/'summary.json') if spec['result_origin']=='NEW_EXECUTION_R6' else load(RUN/'historical_reuse'/spec['scenario']/spec['method']/'recomputed_summary.json')
    for p,h in (load(d/'evidence_hashes.json').items() if spec['result_origin']=='NEW_EXECUTION_R6' else spec['source_files_sha256'].items()):assert sha(d/p)==h
    rows=list(csv.DictReader((d/'per_job.csv').open(encoding='utf8',newline='')));assert len(rows)==80
    jobs={}
    for r in rows:
        jobs[r['job']]={k:(None if r.get(k) in ('',None) else float(r[k])) for k in ('arrival','completion','jct','waiting','training','recovery','progress')};jobs[r['job']]['application']=r['application']
    valid=summary['execution_status']=='COMPLETE' and summary['audit_status']=='PASS' and summary['completed_count']==80
    if valid:
        x=[r['jct'] for r in jobs.values()];assert all(v is not None for v in x)
        recomputed=dict(mean_jct=float(np.mean(x)),median_jct=float(np.quantile(x,.5)),p95_jct=float(np.quantile(x,.95)),p99_jct=float(np.quantile(x,.99)),makespan=max(r['completion'] for r in jobs.values())-min(r['arrival'] for r in jobs.values()))
        for k,v in recomputed.items():assert abs(v-summary[k])<=1e-7
    else:assert all(summary[k] is None for k in ('mean_jct','median_jct','p95_jct','p99_jct','makespan'))
    return summary,jobs

def analyze(manifest,out):
    m=load(manifest);out=Path(out);out.mkdir(parents=True,exist_ok=False);matrix=load(RUN/'matrix_ledger.json')['cells'];sources=[];results=[];all_jobs={};metrics={};integrity={}
    scenarios=list(dict.fromkeys(c['scenario'] for c in m['cells']))
    for cell in matrix:
        spec=dict(scenario=cell['scenario'],method=cell['method'],display_method=cell['method'],result_origin='NEW_EXECUTION_R6',output=cell.get('output'),state=cell['execution_status'],audit_status=cell['audit_status'],logical_cell=cell['index'])
        sources.append(spec)
    for scenario in scenarios:
        for method in ('SIA-SMART-P','CAPRA-FK','CAPRA'):
            qpath=RUN/'historical_reuse'/scenario/method/'reuse_eligibility.json';q=load(qpath) if qpath.exists() else dict(state='UNVERIFIED',reason='Qualification not completed within its fixed budget')
            sources.append(dict(scenario=scenario,method=method,display_method='CAPRA-FKR' if method=='CAPRA' else method,result_origin='REUSED_R4',output=q.get('source_directory'),state='COMPLETE' if q['state']=='ELIGIBLE' else q['state'],audit_status='PASS' if q['state']=='ELIGIBLE' else 'UNVERIFIED',reuse_reason=q.get('reason'),source_commit=R4,source_files_sha256=q.get('source_files_sha256',{})))
    for spec in sources:
        ident=spec['scenario']+'/'+spec['method'];entry={k:v for k,v in spec.items() if k!='source_files_sha256'}
        if spec['output'] and (ROOT/spec['output']/'summary.json').exists() and spec['audit_status']=='PASS':
            s,j=read_source(spec);metrics[ident]=s;all_jobs[ident]=j
            entry.update({k:s.get(k) for k in ('execution_status','audit_status','formal_performance_experiment','expected_job_count','jobs_loaded_count','submitted_count','arrived_count','completed_count','censored_count','mean_jct','median_jct','p95_jct','p99_jct','makespan','total_waiting','total_training','total_recovery','rounds')})
            entry['decision_median']=(s['decision_distribution'] or {}).get('median');entry['decision_p95']=(s['decision_distribution'] or {}).get('p95');entry['decision_p99']=(s['decision_distribution'] or {}).get('p99');entry['decision_max']=(s['decision_distribution'] or {}).get('max')
            if spec['result_origin']=='NEW_EXECUTION_R6':
                process=load(ROOT/spec['output']/'process.json');entry['unit_wall_seconds']=process['charged_seconds'];entry['audit_seconds']=s['audit_recompute_wall_seconds']
                for p,h in load(ROOT/spec['output']/'evidence_hashes.json').items():integrity[(Path(spec['output'])/p).as_posix()]=h
            else:entry['wall_scope']='HISTORICAL_REFERENCE_ONLY';integrity.update({(Path(spec['output'])/p).as_posix():h for p,h in spec['source_files_sha256'].items()})
        else:
            entry.update(expected_job_count=80,jobs_loaded_count=0,submitted_count=0,arrived_count=0,completed_count=0,censored_count=80,execution_status=spec['state'],formal_performance_experiment='NOT_STARTED' if spec['state']=='NOT_STARTED' else spec['state'])
            if spec['output'] and (ROOT/spec['output']/'summary.json').exists():
                observed=load(ROOT/spec['output']/'summary.json')
                for k in ('jobs_loaded_count','submitted_count','arrived_count','completed_count','censored_count'):entry[k]=observed.get(k,entry[k])
            for k in ('mean_jct','median_jct','p95_jct','p99_jct','makespan','total_waiting','total_training','total_recovery','decision_median','decision_p95','decision_p99','decision_max'):entry[k]=None
        results.append(entry)
    comparisons=[];paired=[];worst=[]
    for scenario in scenarios:
        for method,baseline in [('CAPRA-Direct','CAPRA-F-Only'),('CAPRA-F-Only','SIA-SMART-P'),('CAPRA-Direct','SIA-SMART-P'),('CAPRA-Direct','CAPRA-FK'),('CAPRA-Direct','CAPRA')]:
            ida=scenario+'/'+method;idb=scenario+'/'+baseline;c=dict(scenario=scenario,method=method,baseline=baseline,status='MISSING_OR_NOT_COMPLETE',reason=None)
            if ida not in metrics or idb not in metrics or any(metrics[i]['execution_status']!='COMPLETE' or metrics[i]['audit_status']!='PASS' for i in (ida,idb)):
                c['reason']='A required new cell is incomplete/unavailable or R4 baseline was not eligible';comparisons.append(c);continue
            a,b=metrics[ida],metrics[idb];ja,jb=all_jobs[ida],all_jobs[idb];assert set(ja)==set(jb);rows=[]
            for k in sorted(ja):
                x,y=ja[k],jb[k];assert x['arrival']==y['arrival'] and x['application']==y['application']
                delta=x['jct']-y['jct'];row=dict(scenario=scenario,method=method,baseline=baseline,job=k,application=x['application'],method_jct=x['jct'],baseline_jct=y['jct'],delta_jct=delta,ratio=x['jct']/y['jct'],classification='FAST' if delta<-PAIR_EPS else ('SLOW' if delta>PAIR_EPS else 'TIE'))
                for field in ('waiting','training','recovery'):row['method_'+field]=x[field];row['baseline_'+field]=y[field];row['delta_'+field]=x[field]-y[field]
                rows.append(row)
            c.update(status='COMPARED',paired_jobs=80,fast=sum(r['classification']=='FAST' for r in rows),tie=sum(r['classification']=='TIE' for r in rows),slow=sum(r['classification']=='SLOW' for r in rows),ratio_p95=float(np.quantile([r['ratio'] for r in rows],.95)),ratio_max=max(r['ratio'] for r in rows))
            for field in ('mean_jct','median_jct','p95_jct','p99_jct','makespan'):c[field+'_improvement_percent']=100*(b[field]-a[field])/b[field]
            for field in ('waiting','training','recovery'):c['mean_'+field+'_difference']=(a['total_'+field]-b['total_'+field])/80
            maxratio=max(rows,key=lambda r:(r['ratio'],r['delta_jct'],r['job']));maxabsolute=sorted(rows,key=lambda r:(-r['delta_jct'],r['job']))[0]
            c.update(worst_ratio_job=maxratio['job'],worst_absolute_job=maxabsolute['job'],worst_absolute_delta=maxabsolute['delta_jct']);worst.append(dict(comparison=dict(scenario=scenario,method=method,baseline=baseline),worst_ratio=maxratio,worst_absolute=maxabsolute));paired.extend(rows);comparisons.append(c)
    mechanisms=[];quota_changes=[];strata=defaultdict(Counter);cases=[];mechanism_summary=[]
    for scenario in scenarios:
        ident=scenario+'/CAPRA-Direct';cell=next(c for c in matrix if c['scenario']==scenario and c['method']=='CAPRA-Direct')
        if ident not in metrics:continue
        summary=Counter();first_gain=None;first_offset=None;comparison=next(c for c in comparisons if c['scenario']==scenario and c['method']=='CAPRA-Direct' and c['baseline']=='CAPRA-F-Only')
        for r in events(ROOT/cell['output']/'events.jsonl.gz'):
            if not r['plan']:continue
            s=r['selection'];f,d=s['candidates'];summary['nonempty_rounds']+=1;summary['selected_'+s['selected']]+=1;summary['D_'+s['D_status']]+=1
            summary['candidate_wall_above_5s']+=s['candidate_seconds']>5.
            summary['budget_check_calls']+=s['counts']['budget_checks']
            base=dict(scenario=scenario,round=r['round'],time=r['time'],selected=s['selected'],D_status=s['D_status'],jobs=len(r['plan']),locks=len(r['locks']),allocated_gpus=sum(x['gpus'] for x in r['plan'].values()),Phi_F=f['score']['phi'],Phi_D=None,DeltaPhi=None,DeltaR=None,DeltaL=None)
            if not d['feasible']:
                summary['budget_fallback']+=1;base['F_category']='BUDGET_FALLBACK';mechanisms.append(base);continue
            rf,lf,pf=score_parts(f);rd,ld,pd=score_parts(d);dr=rd-rf;dl=ld-lf;dp=pd-pf;assert abs(dp-(dr-dl))<=1e-7
            allocations_equal=same_alloc(f['allocations'],d['allocations']);delaydiff=d['score']['total_delay']-f['score']['total_delay']
            if s['selected']=='D':category='D_SELECTED'
            elif pf>pd+EPS:category='F_STRICT_PHI'
            elif f['score']['total_delay']<d['score']['total_delay']-EPS or f['score']['changes']<d['score']['changes']:category='F_DELAY_CHANGES_TIE_BREAK'
            else:category='F_FINAL_TIE_IDENTICAL_ALLOCATION' if allocations_equal else 'F_FINAL_TIE_DIFFERENT_ALLOCATION'
            flags=dict(raw_sum_rho_up=dr>EPS,total_delay_down=delaydiff<-EPS,same_R_same_total_delay_Phi_diff=abs(dr)<=EPS and abs(delaydiff)<=EPS and abs(dp)>EPS,raw_rho_up_but_F_Phi_higher=dr>EPS and dp<-EPS,D_Phi_higher_cohort_JCT_not_improved=dp>EPS and comparison['status']=='COMPARED' and comparison['mean_jct_improvement_percent']<=0)
            base.update(R_F=rf,R_D=rd,L_F=lf,L_D=ld,Phi_D=pd,DeltaPhi=dp,DeltaR=dr,DeltaL=dl,total_delay_F=f['score']['total_delay'],total_delay_D=d['score']['total_delay'],new_cost_F=f['score']['total_new_cost'],new_cost_D=d['score']['total_new_cost'],complete_allocation_equal=allocations_equal,F_category=category,**flags)
            for label,candidate in [('F',f),('D',d)]:
                pure=0
                for k,a in candidate['allocations'].items():
                    old=r['current'].get(k);batch=r.get('batch_before',{}).get(k)
                    if old and old['node']!=a['node'] and old['gpu_type']==a['gpu_type'] and old['gpus']==a['gpus'] and batch=={q:r['plan'][k][q] for q in ('atomic_bsz','accum_steps')}:pure+=1
                base['pure_node_migrations_'+label]=pure
            cpu_count=ram_count=joint_count=0
            for k,a in f['allocations'].items():
                b=d['allocations'][k];cpu=abs(b['cpu']-a['cpu'])>CAP_EPS;ram=abs(b['ram']-a['ram'])>CAP_EPS;rho=b['rho']-a['rho']
                if not cpu and not ram and abs(rho)<=EPS and a['node']==b['node']:continue
                if abs(rho)<=EPS:kind='QUOTA_OR_NODE_CHANGE_NO_RHO_GAIN'
                elif cpu and not ram:kind='CPU_ONLY_GAIN' if rho>0 else 'CPU_ONLY_LOSS'
                elif ram and not cpu:kind='RAM_ONLY_GAIN' if rho>0 else 'RAM_ONLY_LOSS'
                elif cpu and ram:kind='JOINT_CPU_RAM_GAIN' if rho>0 else 'JOINT_CPU_RAM_LOSS'
                else:kind='RHO_CHANGE_WITHIN_QUOTA_TOLERANCE'
                quota_changes.append(dict(scenario=scenario,round=r['round'],job=k,classification=kind,node_F=a['node'],node_D=b['node'],cpu_F=a['cpu'],cpu_D=b['cpu'],ram_F=a['ram'],ram_D=b['ram'],rho_F=a['rho'],rho_D=b['rho'],delta_rho=rho,selected=s['selected']))
                summary['quota_'+kind]+=1;cpu_count+=cpu;ram_count+=ram;joint_count+=cpu and ram
            base.update(cpu_changed_jobs=cpu_count,ram_changed_jobs=ram_count,joint_changed_jobs=joint_count)
            summary[category]+=1
            for flag,value in flags.items():summary[flag]+=value
            strata[(scenario,len(r['plan']),len(r['locks']),base['allocated_gpus'])][category]+=1
            if dp>EPS and first_gain is None:first_gain=r
            if dr>EPS and dp<-EPS and first_offset is None:first_offset=r
            mechanisms.append(base)
        for kind,event in [('FIRST_D_STRICT_PHI_GAIN',first_gain),('FIRST_RAW_GAIN_OFFSET_BY_RECOVERY',first_offset)]:
            cases.append(dict(scenario=scenario,case=kind,status='FOUND' if event else 'ABSENT',event=event,scope='Same-state candidates on Direct trajectory, not the F-only counterfactual trajectory'))
        paired_direct=[r for r in paired if r['scenario']==scenario and r['method']=='CAPRA-Direct' and r['baseline']=='CAPRA-F-Only' and r['delta_jct']>PAIR_EPS]
        hit=sorted(paired_direct,key=lambda r:(-r['delta_jct'],r['job']))[0] if paired_direct else None
        if hit:
            traces={}
            for method in ('CAPRA-Direct','CAPRA-F-Only'):
                path=next(c['output'] for c in matrix if c['scenario']==scenario and c['method']==method)
                traces[method]=[dict(round=r['round'],time=r['time'],plan=r['plan'].get(hit['job']),allocation=r['allocations'].get(hit['job']),locked=r['locks'].get(hit['job']),prediction=r['commit_predictions'].get(hit['job']),execution=next((e for e in r['executions'] if e['job']==hit['job']),None),transitions=[e for e in r['transitions'] if e['job']==hit['job']]) for r in events(ROOT/path/'events.jsonl.gz') if hit['job'] in r['plan'] or any(e['job']==hit['job'] for e in r['executions'])]
            cases.append(dict(scenario=scenario,case='MAX_ABSOLUTE_JCT_DEGRADATION_VS_F_ONLY',status='FOUND',paired_job=hit,trajectories=traces,warning='Whole trajectories diverge; this is not causal attribution to one D action'))
        else:cases.append(dict(scenario=scenario,case='MAX_ABSOLUTE_JCT_DEGRADATION_VS_F_ONLY',status='ABSENT'))
        mechanism_summary.append(dict(scenario=scenario,counts=dict(summary),flag_scope='Nonexclusive flags overlap; do not add or subtract them as a partition'))
    fields=sorted({k for r in results for k in r});table(out/'results.csv',results,fields);dump(out/'results.json',results);dump(out/'source_index.json',sources);dump(out/'metrics.json',metrics)
    table(out/'comparisons.csv',comparisons,sorted({k for r in comparisons for k in r}));dump(out/'comparisons.json',comparisons);table(out/'paired_jobs.csv',paired);dump(out/'worst_cases.json',worst)
    table(out/'mechanism_rounds.csv',mechanisms,sorted({k for r in mechanisms for k in r}));table(out/'quota_changes.csv',quota_changes);dump(out/'mechanism_summary.json',mechanism_summary);dump(out/'representative_cases.json',cases)
    table(out/'mechanism_strata.csv',[dict(scenario=k[0],jobs=k[1],locks=k[2],gpus=k[3],**v) for k,v in strata.items()],sorted({'scenario','jobs','locks','gpus'}|{x for v in strata.values() for x in v}))
    overhead=[dict(scenario=s['scenario'],method=s['method'],origin=s['result_origin'],**{k:s.get(k) for k in ('decision_median','decision_p95','decision_p99','decision_max','unit_wall_seconds','audit_seconds')}) for s in results]
    table(out/'overhead.csv',overhead);dump(out/'raw_integrity.json',dict(status='PASS',files_sha256=integrity,no_simulation_or_layout_search=True))
    for p,h in integrity.items():assert sha(ROOT/p)==h
    return dict(sources=sources,results=results,comparisons=comparisons,mechanism_summary=mechanism_summary,mechanism_rows=mechanisms,metrics=metrics,output=out)
