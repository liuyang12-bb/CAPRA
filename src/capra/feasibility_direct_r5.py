"""Boolean two-bin completion only; no layout witness or objective optimization."""
import math
from collections import defaultdict
from .node_allocator import CAP_EPS

def check_scope(nodes,contract):
    groups=defaultdict(list)
    assert len({n.id for n in nodes})==len(nodes),'DUPLICATE_NODE_ID'
    for n in nodes:
        if not isinstance(n.gpus,int) or n.gpus<=0 or not all(math.isfinite(x) and x>0 for x in (n.cpu,n.ram)):
            raise ValueError('UNSUPPORTED_SCOPE: invalid node capacity')
        groups[n.gpu_type].append(n)
    if any(len(ns)>2 for ns in groups.values()):raise ValueError('UNSUPPORTED_SCOPE: more than two nodes per GPU type')
    for k,p in contract.items():
        if p['nodes']!=1:raise ValueError('UNSUPPORTED_SCOPE: multi-node job')
        assert p['name']==k and isinstance(p['gpus'],int) and p['gpus']>0
        assert p['gpu_type'] in groups,'UNKNOWN_GPU_TYPE'
    return groups

def proportional_legal(k,n,contract,apps,response):
    p=contract[k];g=p['gpus']
    return p['gpu_type']==n.gpu_type and g<=n.gpus and response.legal(g,g*n.cpu/n.gpus,g*n.ram/n.gpus,n)

def can_finish(contract,nodes,apps,response,locks,layout,remaining):
    """Reserve actual locks and reclaimable proportional nonlocks, then boolean DP."""
    groups=check_scope(nodes,contract);nm={n.id:n for n in nodes};rest=sorted(remaining)
    def no(reason,**details):return dict(feasible=False,reason=reason,**details)
    if set(layout)&set(rest) or set(layout)|set(rest)!=set(contract):return no('PARTITION_MISMATCH')
    if not set(locks)<=set(layout):return no('LOCK_NOT_RESERVED')
    used={n.id:[0,0.,0.] for n in nodes}
    for k,nid in sorted(layout.items()):
        if k not in contract or nid not in nm:return no('UNKNOWN_JOB_OR_NODE')
        n=nm[nid];p=contract[k];g=p['gpus']
        if p['gpu_type']!=n.gpu_type or g>n.gpus:return no('GPU_TYPE_OR_SHAPE',job=k,node=nid)
        if k in locks:
            a=locks[k]
            if a.node!=nid or (a.gpu_type,a.gpus)!=(p['gpu_type'],g):return no('LOCK_CHANGED',job=k)
            c,m=a.cpu,a.ram
            if not response.legal(g,c,m,n):return no('LOCK_PROFILE_DOMAIN',job=k)
        else:
            if not proportional_legal(k,n,contract,apps,response):return no('PROPORTIONAL_DOMAIN',job=k,node=nid)
            c,m=g*n.cpu/n.gpus,g*n.ram/n.gpus
        for i,v in enumerate((g,c,m)):used[nid][i]+=v
    capacities={};reservations={}
    for n in sorted(nodes,key=lambda n:n.id):
        u=used[n.id];free=[n.gpus-u[0],n.cpu-u[1],n.ram-u[2]]
        if any(x < -CAP_EPS for x in free):return no('PARTIAL_CAPACITY',node=n.id,used=u)
        candidates=[k for k in range(int(free[0])+1) if k*n.cpu/n.gpus<=free[1]+CAP_EPS and k*n.ram/n.gpus<=free[2]+CAP_EPS]
        if not candidates:return no('NO_ZERO_CAPACITY',node=n.id)
        capacities[n.id]=max(candidates);reservations[n.id]=dict(used=u,remaining=free,effective_gpus=capacities[n.id])
    checks=[]
    for typ,unsorted in sorted(groups.items()):
        ns=sorted(unsorted,key=lambda n:n.id);js=[k for k in rest if contract[k]['gpu_type']==typ]
        allowed={k:[n.id for n in ns if proportional_legal(k,n,contract,apps,response) and contract[k]['gpus']<=capacities[n.id]] for k in js}
        record=dict(gpu_type=typ,jobs=js,allowed_nodes=allowed,effective_capacities={n.id:capacities[n.id] for n in ns});checks.append(record)
        if any(not allowed[k] for k in js):return no('NO_LEGAL_REMAINING_NODE',reservations=reservations,groups=checks)
        if len(ns)==1:
            if sum(contract[k]['gpus'] for k in js)>capacities[ns[0].id]:return no('ONE_BIN_NO_COMPLETION',reservations=reservations,groups=checks)
        else:
            b0,b1=(capacities[n.id] for n in ns);reachable={0};total=0
            for k in js:
                g=contract[k]['gpus'];next_states=set()
                for left in reachable:
                    right=total-left
                    if ns[0].id in allowed[k] and left+g<=b0 and right<=b1:next_states.add(left+g)
                    if ns[1].id in allowed[k] and left<=b0 and right+g<=b1:next_states.add(left)
                total+=g;reachable=next_states
                if not reachable:return no('TWO_BIN_NO_COMPLETION',reservations=reservations,groups=checks)
            if not any(total-left<=b1 for left in reachable):return no('TWO_BIN_NO_COMPLETION',reservations=reservations,groups=checks)
    return dict(feasible=True,reason='COMPLETE_EXTENSION_EXISTS',reservations=reservations,groups=checks)
