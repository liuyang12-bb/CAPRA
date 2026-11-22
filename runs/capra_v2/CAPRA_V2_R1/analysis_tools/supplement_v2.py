"""Post-experiment raw statistics only; no scheduler, optimizer or model execution."""
from pathlib import Path
from collections import Counter
import csv,gzip,json
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parents[1]
results=json.loads((OUT/'results.json').read_text(encoding='utf8'))
nodes={n['id']:n for n in json.loads((ROOT/'configs/cluster.json').read_text())}
cpu_axis=json.loads((ROOT/'data/responses.json').read_text())['cpu_axis']
analysis=[];application_rows=[]
for r in results:
    if r.get('audit')!='PASS':continue
    directory=ROOT/r['output'];per=list(csv.DictReader((directory/'per_job.csv').open(encoding='utf8',newline='')))
    apps={j['job']:j['application'] for j in per}
    active=0;chosen=Counter();positive=Counter();tot=Counter();examples={};individual_drop=0;lower_rho=0;partitions=0
    with gzip.open(directory/'events.jsonl.gz','rt',encoding='utf8') as stream:
        for line in stream:
            x=json.loads(line)
            if x['plan']:
                active+=1;chosen[x['selection']['selected']]+=1
                cs={c['label']:c for c in x['selection']['candidates']}
                if 'F' in cs:
                    f=cs['F'];s=cs[x['selection']['selected']]
                    for label in ('K','R'):
                        c=cs.get(label)
                        if c and c['feasible'] and c['score']['phi']>f['score']['phi']+1e-9:positive[label]+=1
                    if any(s['score']['jobs'][k]['contribution']<f['score']['jobs'][k]['contribution']-1e-9 for k in x['plan']):individual_drop+=1
                    if sum(a['rho'] for a in s['allocations'].values())<sum(a['rho'] for a in f['allocations'].values())-1e-9:lower_rho+=1
                    c=cs.get('R')
                    if c and c['feasible']:
                        ks=sorted(x['plan'])
                        partitions+=any((c['allocations'][k]['node']==c['allocations'][j]['node'])!=(f['allocations'][k]['node']==f['allocations'][j]['node']) for k in ks for j in ks)
            for e in x['executions']:
                if e['training']<=0:continue
                a=e['allocation'];app=apps[e['job']];g=a['gpus'];seconds=e['training'];tot['training_seconds']+=seconds
                sample=dict(round=x['round'],time=x['time'],job=e['job'],application=app,gpus=g,cpu=a['cpu'],ram=a['ram'],rho=a['rho'],training_seconds=seconds)
                if not any(abs(a['cpu']-v*g)<1e-7 for v in cpu_axis):
                    tot['intermediate_cpu_training_intervals']+=1;tot['intermediate_cpu_training_seconds']+=seconds
                    examples.setdefault('intermediate_cpu',sample)
                if app=='bert' and a['cpu']<3*g-1e-7 and abs(a['rho']-1)<1e-7:
                    tot['bert_reclaimed_training_intervals']+=1;examples.setdefault('bert_reclaimed',sample)
                if app=='cifar10':
                    tot['cifar_training_seconds']+=seconds
                    if g==nodes[a['node']]['gpus']:
                        tot['cifar_full_node_training_seconds']+=seconds
                        assert abs(a['rho']-1)<1e-7
    analysis.append(dict(workload=r['workload'],method=r['method'],active_decisions=active,selected_active=dict(chosen),positive_phi_over_F_active=dict(positive),
        selected_with_some_individual_window_drop=individual_drop,selected_with_lower_raw_sum_rho_than_F=lower_rho,R_non_equivalent_partition_rounds=partitions,
        counters=dict(tot),cifar_full_node_training_fraction=tot['cifar_full_node_training_seconds']/tot['cifar_training_seconds'] if tot['cifar_training_seconds'] else None,
        examples=examples,scope='Observed executions and same-state candidate model scores; not a causal JCT counterfactual or new experiment.'))
    for app in sorted(set(apps.values())):
        js=[j for j in per if j['application']==app]
        application_rows.append(dict(workload=r['workload'],method=r['method'],application=app,jobs=len(js),**{'mean_'+k:sum(float(j[k]) for j in js)/len(js) for k in ('jct','waiting','training','recovery')}))
(OUT/'raw_opportunity_analysis.json').write_text(json.dumps(analysis,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
with (OUT/'application_time_and_jct.csv').open('w',encoding='utf8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(application_rows[0]));w.writeheader();w.writerows(application_rows)
print(json.dumps([dict(workload=x['workload'],method=x['method'],active=x['active_decisions'],chosen=x['selected_active'],positive_phi=x['positive_phi_over_F_active'],full_node_cifar_fraction=x['cifar_full_node_training_fraction'],intermediate_cpu=x['counters'].get('intermediate_cpu_training_intervals',0),bert_reclaims=x['counters'].get('bert_reclaimed_training_intervals',0),individual_drop=x['selected_with_some_individual_window_drop'],lower_rho=x['selected_with_lower_raw_sum_rho_than_F']) for x in analysis],ensure_ascii=False,indent=2))
