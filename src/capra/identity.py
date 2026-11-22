"""Two equivalent nodes: compare identity/swap, never enumerate general permutations."""
from dataclasses import replace
from .costs import evaluate,EPS

def stabilize(allocations,nodes,current,locks,remaining,apps,costs,started):
    result=dict(allocations);mappings=[]
    groups={}
    for n in nodes:groups.setdefault((n.gpu_type,n.gpus,n.cpu,n.ram),[]).append(n.id)
    for spec,ids in sorted(groups.items()):
        ids=sorted(ids)
        assert len(ids)<=2,'V2_IDENTITY_SCOPE_MAX_TWO_EQUIVALENT_NODES'
        if len(ids)<2:continue
        before=evaluate(result,current,locks,remaining,apps,costs,started)
        swap={ids[0]:ids[1],ids[1]:ids[0]}
        alternative={k:replace(a,node=swap.get(a.node,a.node)) for k,a in result.items()}
        valid=all(alternative.get(k)==a for k,a in locks.items())
        chosen='identity';after=before
        if valid:
            other=evaluate(alternative,current,locks,remaining,apps,costs,started)
            canonical=lambda d:tuple((k,a.node) for k,a in sorted(d.items()))
            if other['total_delay']<before['total_delay']-EPS or (abs(other['total_delay']-before['total_delay'])<=EPS and canonical(alternative)<canonical(result)):
                result=alternative;chosen='swap';after=other
        mappings.append(dict(nodes=ids,choice=chosen,swap_feasible=valid,before_delay=before['total_delay'],after_delay=after['total_delay']))
    return result,dict(groups=mappings,before_delay=evaluate(allocations,current,locks,remaining,apps,costs,started)['total_delay'],after_delay=evaluate(result,current,locks,remaining,apps,costs,started)['total_delay'])

def reference(plan,nodes,current,locks,remaining,apps,costs,started,response):
    from .tune import proportional
    from .contracts import validate,serialized
    nm={n.id:n for n in nodes}
    base={k:(locks[k] if k in locks else proportional(p,nm[p.node],response,apps[k])) for k,p in plan.items()}
    validate(plan,base,nodes,locks)
    stable,meta=stabilize(base,nodes,current,locks,remaining,apps,costs,started)
    updated={k:replace(p,node=stable[k].node) for k,p in plan.items()}
    validate(updated,stable,nodes,locks)
    return updated,dict(before=serialized(base),after=serialized(stable),mapping=meta)
