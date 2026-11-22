"""Pure transition semantics shared by v2 identity mapping, scoring and commit."""
EPS=1e-9

def application_costs(jobs):
    costs={}
    for job in jobs:
        values={t:float(a.rescale_time or 30) for t,a in job.applications.items()}
        if job.app_name in costs:assert costs[job.app_name]==values
        costs[job.app_name]=values
    return costs

def gpu_key(a):
    return None if a is None else (a.node,a.gpu_type,a.gpus)

def transition(name,new,current,locks,remaining,apps,costs,started):
    old=current.get(name)
    if name in locks:
        assert new==locks[name] and old==locks[name],'LOCK_TRANSITION'
        d=float(remaining[name]);assert d>0
        return dict(kind='locked',new_cost=0.0,existing_remaining=d,delay=d,gpu_change=False)
    if new is None:
        return dict(kind='suspend' if old is not None else 'unchanged',new_cost=0.0,existing_remaining=0.0,delay=0.0,gpu_change=old is not None)
    if gpu_key(old)==gpu_key(new):
        return dict(kind='unchanged' if old==new else 'aux_update',new_cost=0.0,existing_remaining=0.0,delay=0.0,gpu_change=False)
    kind=('resume' if name in started else 'start') if old is None else ('migration' if old.node!=new.node else 'reconfigure')
    cost=float(costs[apps[name]][new.gpu_type])
    return dict(kind=kind,new_cost=cost,existing_remaining=0.0,delay=cost,gpu_change=True)

def evaluate(allocations,current,locks,remaining,apps,costs,started,horizon=180.0):
    ts={k:transition(k,a,current,locks,remaining,apps,costs,started) for k,a in sorted(allocations.items())}
    scores={k:dict(**t,effective_window=max(0.0,horizon-t['delay']),rho=allocations[k].rho,
        contribution=allocations[k].rho*max(0.0,1.0-t['delay']/horizon)) for k,t in ts.items()}
    return dict(phi=sum(v['contribution'] for v in scores.values()),total_delay=sum(t['delay'] for t in ts.values()),
        total_new_cost=sum(t['new_cost'] for t in ts.values()),changes=sum(t['gpu_change'] for t in ts.values()),jobs=scores)
