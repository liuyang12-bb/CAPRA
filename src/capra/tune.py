"""Single-node reimplementation of Synergy-TUNE, not a call to its deployment stack.

Try profiled demand -> current fair share -> relevant peers' fair share -> complete
proportional baseline. Nodes use dynamic least-free-GPU best fit with ID tie-break.
No swaps, global resource MIP, ETA objective, or extra admission policy.
"""
from dataclasses import replace
from .contracts import Allocation, validate


def proportional(p, node, response, app):
    c, m = node.cpu*p.gpus/node.gpus, node.ram*p.gpus/node.gpus
    return Allocation(node.id,p.gpu_type,p.gpus,c,m,response.rho(app,p.gpus,c,m))


def allocate(plan, nodes, apps, response, mode='free', locks=None):
    assert mode in ('free','fixed','proportional')
    locks = dict(locks or {})
    node_map = {n.id:n for n in nodes}
    result = dict(locks)
    events = []

    def fits(candidate, existing):
        n = node_map[candidate.node]
        peers = [a for a in existing.values() if a.node == n.id]
        return all(sum(getattr(a,k) for a in peers)+getattr(candidate,k)<=getattr(n,k)+1e-8 for k in ('gpus','cpu','ram'))

    # GPU count ordering follows Sia's placement packing; job-name is stable tie-break.
    for name,p in sorted(plan.items(),key=lambda kv:(-kv[1].gpus,kv[0])):
        if name in locks:
            continue
        candidates = [n for n in nodes if n.gpu_type==p.gpu_type and (mode=='free' or n.id==p.node)]
        candidates.sort(key=lambda n:(n.gpus-sum(a.gpus for a in result.values() if a.node==n.id),n.id))
        demands = {}
        for n in candidates:
            c,m = response.preferred(apps[name],p.gpus,n) if mode!='proportional' else (n.cpu*p.gpus/n.gpus,n.ram*p.gpus/n.gpus)
            a = Allocation(n.id,p.gpu_type,p.gpus,c,m,response.rho(apps[name],p.gpus,c,m))
            demands[n.id] = a
        found = False
        for phase in ('profiled','current_proportional','peer_proportional'):
            if mode=='proportional' and phase!='profiled':
                continue
            for n in candidates:
                trial = dict(result)
                a = demands[n.id] if phase=='profiled' else proportional(p,n,response,apps[name])
                if phase=='peer_proportional':
                    for peer,b in list(trial.items()):
                        if b.node==n.id and peer not in locks:
                            fair = proportional(plan[peer],n,response,apps[peer])
                            # Switching peer to fair share cannot degrade below fair-share performance.
                            trial[peer] = fair
                if fits(a,trial):
                    changed = [k for k in trial if trial[k]!=result[k]]
                    result=trial; result[name]=a; found=True
                    if phase!='profiled':
                        events.append(dict(job=name,reason=phase,peers=changed,node=n.id))
                    break
            if found:
                break
        if not found:
            # Complete verified baseline from the GPU stage, never partial success.
            baseline = {k:(locks[k] if k in locks else proportional(q,node_map[q.node],response,apps[k])) for k,q in plan.items()}
            validate(plan,baseline,nodes,locks)
            events.append(dict(job=name,reason='COMPLETE_SIA_PROPORTIONAL_FALLBACK',discarded_partial=list(result)))
            return baseline,events
    validate(plan,result,nodes,locks)
    for name,a in result.items():
        fair=proportional(plan[name],node_map[a.node],response,apps[name])
        assert a.rho+1e-8>=fair.rho, ('PROPORTIONAL_PERFORMANCE_GUARD',name)
    return result,events
