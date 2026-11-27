"""Read-only strict nested new-colocation funnel; no optimizer or simulation imports."""
from collections import Counter
from itertools import combinations
EPS=1e-9
STAGES={
 'A':'nonempty complete GPU plan',
 'B':'same-GPU-type CPU/RAM donor-receiver pair exists',
 'C':'some B pair GPU sum fits a same-type node',
 'D':'some C pair not colocated in any feasible F/K (P for smart)',
 'E':'some D pair has complete proportional-plus-lock direct-move witness',
 'F':'actual feasible R candidate covers some E pair',
 'G':'F and actual R gross sum-rho exceeds best F/K',
 'H':'G and recovery-adjusted original rule selects R',
 'I':'H and current actual training has positive auxiliary gain'}
def best_reference(candidates):
    valid=[c for c in candidates if c['feasible'] and c['label'] in ('F','K','P')]
    assert valid
    selected=valid[0]
    for c in valid[1:]:
        a,b=c['score'],selected['score']
        if a['phi']>b['phi']+EPS or (abs(a['phi']-b['phi'])<=EPS and (a['total_delay']<b['total_delay']-EPS or (abs(a['total_delay']-b['total_delay'])<=EPS and a['changes']<b['changes']))):selected=c
    return selected,valid
def legal_vector(plan,layout,nodes,locks,response,apps):
    if set(plan)!=set(layout):return None,['incomplete_job_set']
    use={n:[0.,0.,0.] for n in nodes};out={};reasons=[]
    for k,p in plan.items():
        nid=layout[k]
        if nid not in nodes or nodes[nid]['gpu_type']!=p['gpu_type']:return None,['different_gpu_pool']
        n=nodes[nid];g=p['gpus']
        if k in locks:
            if locks[k]['node']!=nid:return None,['recovery_lock_blocked']
            a=dict(locks[k])
        else:
            cpu=n['cpu']*g/n['gpus'];ram=n['ram']*g/n['gpus']
            a=dict(node=nid,gpu_type=p['gpu_type'],gpus=g,cpu=cpu,ram=ram,rho=response.rho(apps[k],g,cpu,ram))
        for f in ('cpu','ram'):
            if not response.data[f+'_axis'][0]*g-EPS<=a[f]<=min(n[f],response.data[f+'_axis'][-1]*g)+EPS:return None,['profile_domain_'+f]
        out[k]=a
        for i,f in enumerate(('gpus','cpu','ram')):use[nid][i]+=a[f]
    for nid,u in use.items():
        for value,f in zip(u,('gpus','cpu','ram')):
            if value>nodes[nid][f]+1e-7:reasons.append('direct_move_capacity_'+f)
    return (None,reasons) if reasons else (out,[])
def funnel_round(r,nodes,response,apps,role_cache=None):
    role_cache={} if role_cache is None else role_cache
    p=r['plan'];flags=set();allpairs=[];same=[];fits=[];remaining=[];witness=[]
    reference,refs=best_reference(r['selection']['candidates'])
    def roles(k):
        x=p[k];g=x['gpus'];key=(apps[k],x['gpu_type'],g)
        if key not in role_cache:
            n=next(n for n in nodes.values() if n['gpu_type']==x['gpu_type']);cp=n['cpu']*g/n['gpus'];mp=n['ram']*g/n['gpus'];base=response.rho(apps[k],g,cp,mp);d={}
            for f,v in [('cpu',cp),('ram',mp)]:
                d[f+'_donor']=any(z*g<v-EPS and response.rho(apps[k],g,z*g if f=='cpu' else cp,z*g if f=='ram' else mp)>=base-EPS for z in response.data[f+'_axis'])
                top=min(n[f],response.data[f+'_axis'][-1]*g)
                d[f+'_receiver']=response.rho(apps[k],g,top if f=='cpu' else cp,top if f=='ram' else mp)>base+EPS
            role_cache[key]=d
        return role_cache[key]
    for a,b in combinations(sorted(p),2):
        ra,rb=roles(a),roles(b)
        for resource in ('cpu','ram'):
            if not ((ra[resource+'_donor'] and rb[resource+'_receiver']) or (rb[resource+'_donor'] and ra[resource+'_receiver'])):continue
            pair=(a,b,resource);allpairs.append(pair)
            if p[a]['gpu_type']!=p[b]['gpu_type']:flags.add('different_gpu_pool');continue
            same.append(pair)
            if not any(p[a]['gpus']+p[b]['gpus']<=n['gpus'] for n in nodes.values() if n['gpu_type']==p[a]['gpu_type']):flags.add('pair_gpu_sum_exceeds_node');continue
            fits.append(pair)
            if any(c['allocations'][a]['node']==c['allocations'][b]['node'] for c in refs):flags.add('already_colocated_in_F_or_K');continue
            remaining.append(pair)
            for c in refs:
                layout={k:x['node'] for k,x in c['allocations'].items()}
                for moving,peer in ((a,b),(b,a)):
                    if moving in r['locks']:flags.add('recovery_lock_blocked');continue
                    trial=dict(layout);trial[moving]=layout[peer]
                    allocation,reasons=legal_vector(p,trial,nodes,r['locks'],response,apps)
                    flags.update(reasons)
                    if allocation is not None:
                        witness.append(dict(pair=list(pair),reference=c['label'],moving=moving,target=layout[peer],layout=trial,allocations=allocation,scope='Sufficient direct whole-set proportional-plus-lock certificate, not positive net gain'))
    rc=next((c for c in r['selection']['candidates'] if c['label']=='R'),None)
    if rc is None:flags.add('R_not_generated_by_protocol')
    elif not rc['feasible']:flags.add('R_infeasible:'+rc['reason'])
    covered=[w for w in witness if rc and rc['feasible'] and rc['allocations'][w['pair'][0]]['node']==rc['allocations'][w['pair'][1]]['node']]
    rho_ref=sum(a['rho'] for a in reference['allocations'].values());gross=net=None
    if rc and rc['feasible']:
        gross=sum(a['rho'] for a in rc['allocations'].values())-rho_ref;net=rc['score']['phi']-reference['score']['phi']
        if gross<=EPS:flags.add('R_gross_gain_insufficient')
        if net<=EPS:flags.add('R_net_phi_not_strictly_higher')
        if gross>EPS and net<=EPS:flags.add('gross_gain_offset_by_recovery_or_window')
        if witness and not covered:flags.add('R_candidate_misses_direct_pair_witness')
    selected=r['selection']['selected']=='R'
    if selected and gross is not None and gross<=EPS:flags.add('R_selected_cost_or_tie_only')
    positive=sum(e['training'] for e in r['executions'] if e['allocation'] and e['allocation']['rho']>response.rho(apps[e['job']],e['allocation']['gpus'],nodes[e['allocation']['node']]['cpu']*e['allocation']['gpus']/nodes[e['allocation']['node']]['gpus'],nodes[e['allocation']['node']]['ram']*e['allocation']['gpus']/nodes[e['allocation']['node']]['gpus'])+EPS)
    conditions=[bool(p),bool(same),bool(fits),bool(remaining),bool(witness),bool(covered),gross is not None and gross>EPS,selected,positive>EPS]
    values=[];alive=True
    for v in conditions:alive=alive and v;values.append(bool(alive))
    stages=dict(zip(STAGES,values));assert all(not b or a for a,b in zip(values,values[1:]))
    if selected and not stages['H']:flags.add('R_selected_outside_strict_new_colocation_funnel')
    if not same and p:flags.add('no_same_type_resource_complement')
    free={typ:sum(n['gpus'] for n in nodes.values() if n['gpu_type']==typ)-sum(x['gpus'] for x in p.values() if x['gpu_type']==typ) for typ in sorted({n['gpu_type'] for n in nodes.values()})}
    return dict(round=r['round'],time=r['time'],denominator_nonempty=bool(p),stages=stages,nonexclusive_tags=sorted(flags),selected_jobs=sorted(p),gpu_free_by_type=free,pairs_all_resource_complement=[list(x) for x in allpairs],pairs_same_type=[list(x) for x in same],pairs_gpu_fits=[list(x) for x in fits],pairs_not_FK_covered=[list(x) for x in remaining],direct_legal_witnesses=witness,R_covered_witness_pairs=[w['pair'] for w in covered],best_reference=reference['label'],reference_phi=reference['score']['phi'],reference_sum_rho=rho_ref,R_gross_delta=gross,R_net_phi_delta=net,R_selected=selected,R_positive_aux_training_seconds=positive if selected else 0.,R_candidate_generated=rc is not None)
