"""Exactly F/K/R; bounded two-bin GPU DP, shared quotas and fixed H=180 scoring."""
from dataclasses import replace
import time
from .contracts import validate,serialized
from .costs import evaluate,transition,EPS
from .identity import stabilize
from .node_allocator import NodeAllocator

HORIZON=180.0

class CandidateInfeasible(Exception):pass

class Placement:
    def __init__(self,plan,nodes,apps,response,current,locks,remaining,costs,started):
        self.plan=plan;self.nodes=nodes;self.nm={n.id:n for n in nodes};self.apps=apps;self.response=response
        self.current=current;self.locks=locks;self.remaining=remaining;self.costs=costs;self.started=started
        self.allocator=NodeAllocator(plan,nodes,apps,response,current,locks)
        self.mapping_seconds=0.0;self.dp_checks=0

    def reserved(self,layout):
        out={}
        for n in self.nodes:
            ids=[k for k,v in layout.items() if v==n.id]
            if ids:out.update(self.allocator.baseline(n,ids))
        return out

    def can_add(self,layout,k,nid):
        p=self.plan[k];n=self.nm[nid]
        if p.gpu_type!=n.gpu_type:return False
        try:self.reserved(dict(layout,**{k:nid}));return True
        except AssertionError:return False

    def gpu_feasible(self,layout,remaining):
        self.dp_checks+=1
        for typ in sorted({n.gpu_type for n in self.nodes}):
            ns=sorted([n for n in self.nodes if n.gpu_type==typ],key=lambda n:n.id)
            assert len(ns)<=2,'V2_GPU_DP_SCOPE'
            js=[k for k in remaining if self.plan[k].gpu_type==typ]
            free=[n.gpus-sum(self.plan[k].gpus for k,v in layout.items() if v==n.id) for n in ns]
            if len(ns)==1:
                if sum(self.plan[k].gpus for k in js)>free[0] or not all(self.can_add(layout,k,ns[0].id) for k in js):return False
                continue
            reachable={0};total=0
            for k in sorted(js):
                g=self.plan[k].gpus;total+=g
                allowed=[self.can_add(layout,k,n.id) for n in ns]
                reachable=({x+g for x in reachable if x+g<=free[0]} if allowed[0] else set()) | (reachable if allowed[1] else set())
                if not reachable:return False
            if not any(x<=free[0] and total-x<=free[1] for x in reachable):return False
        return True

    def finish(self,label,alloc,quota_meta):
        before=serialized(alloc);began=time.perf_counter()
        a,mapping=stabilize(alloc,self.nodes,self.current,self.locks,self.remaining,self.apps,self.costs,self.started)
        validate(self.plan,a,self.nodes,self.locks)
        score=evaluate(a,self.current,self.locks,self.remaining,self.apps,self.costs,self.started,HORIZON)
        self.mapping_seconds+=time.perf_counter()-began
        return dict(label=label,feasible=True,reason=None,allocations=a,mapping_before=before,mapping=mapping,score=score,quota=quota_meta)

    def fixed(self):
        layout={k:p.node for k,p in self.plan.items()}
        a,meta=self.allocator.layout(layout)
        result=self.finish('F',a,meta)
        assert all(x.node==self.plan[k].node for k,x in result['allocations'].items()),'F_CHANGED_STABLE_REFERENCE'
        return result

    def retained(self):
        layout={k:a.node for k,a in self.locks.items()}
        for k,p in sorted(self.plan.items()):
            old=self.current.get(k)
            if k not in layout and old is not None and (old.gpu_type,old.gpus)==(p.gpu_type,p.gpus):layout[k]=old.node
        try:self.reserved(layout)
        except AssertionError:raise CandidateInfeasible('K_CURRENT_PROPORTIONAL_RESERVATION_INFEASIBLE')
        todo=sorted(set(self.plan)-set(layout),key=lambda k:(-self.plan[k].gpus,k))
        if not self.gpu_feasible(layout,todo):raise CandidateInfeasible('K_PINNED_GPU_FRAGMENTATION')
        while todo:
            k=todo.pop(0);options=[]
            for n in self.nodes:
                if not self.can_add(layout,k,n.id):continue
                trial=dict(layout,**{k:n.id})
                if not self.gpu_feasible(trial,todo):continue
                d=transition(k,self.reserved(trial)[k],self.current,self.locks,self.remaining,self.apps,self.costs,self.started)['delay']
                free=n.gpus-sum(self.plan[j].gpus for j,v in layout.items() if v==n.id)
                options.append(((d,free,n.id),n.id))
            if not options:raise CandidateInfeasible('K_NO_COMPLETE_DETERMINISTIC_EXTENSION')
            layout[k]=min(options)[1]
        a,m=self.allocator.layout(layout)
        return self.finish('K',a,m)

    def reordered(self):
        layout={k:a.node for k,a in self.locks.items()};todo=set(self.plan)-set(layout)
        if not self.gpu_feasible(layout,todo):raise CandidateInfeasible('R_INITIAL_GPU_FRAGMENTATION')
        while todo:
            choices=[]
            for k in sorted(todo):
                p=self.plan[k]
                allowed=[n for n in self.nodes if self.can_add(layout,k,n.id) and self.gpu_feasible(dict(layout,**{k:n.id}),todo-{k})]
                if not allowed:raise CandidateInfeasible('R_NO_FEASIBLE_NODE_FOR_REMAINING_JOB')
                n=allowed[0];c,m=self.response.preferred(self.apps[k],p.gpus,n)
                pressure=max(0,c/n.cpu-p.gpus/n.gpus,m/n.ram-p.gpus/n.gpus)
                forced=p.gpus==n.gpus or len(allowed)==1
                choices.append(((0 if forced else 1,-round(pressure,12),-p.gpus,k),k,allowed))
            _,k,allowed=min(choices,key=lambda x:x[0]);options=[]
            for n in allowed:
                ids=[j for j,v in layout.items() if v==n.id]
                before,_=self.allocator.solve(n.id,ids);after,_=self.allocator.solve(n.id,ids+[k])
                gain=sum(a.rho for a in after.values())-sum(a.rho for a in before.values())
                current_node=self.current.get(k)
                keep=current_node is not None and current_node.node==n.id
                d=transition(k,after[k],self.current,self.locks,self.remaining,self.apps,self.costs,self.started)['delay']
                options.append(((-round(gain,12),0 if keep else 1,d,n.id),n.id))
            layout[k]=min(options)[1];todo.remove(k)
        a,m=self.allocator.layout(layout)
        return self.finish('R',a,m)

    def select(self,method):
        began=time.perf_counter();candidates=[]
        if method=='SIA-P':
            a=self.reserved({k:p.node for k,p in self.plan.items()})
            selected=self.finish('P',a,{})
            assert all(a.node==self.plan[k].node for k,a in selected['allocations'].items())
            candidates=[selected]
        else:
            f=self.fixed();candidates=[f];selected=f
            if method=='CAPRA':
                for label,fn in (('K',self.retained),('R',self.reordered)):
                    try:c=fn()
                    except CandidateInfeasible as error:
                        candidates.append(dict(label=label,feasible=False,reason=str(error)));continue
                    candidates.append(c)
                    a,b=c['score'],selected['score']
                    better=a['phi']>b['phi']+EPS
                    if abs(a['phi']-b['phi'])<=EPS:
                        better=(a['total_delay']<b['total_delay']-EPS or (abs(a['total_delay']-b['total_delay'])<=EPS and a['changes']<b['changes']))
                    if better:selected=c
            assert selected['score']['phi']+EPS>=f['score']['phi'],'F_INCUMBENT_GUARD'
        record=[]
        for c in candidates:
            d=dict(c)
            if c['feasible']:d['allocations']=serialized(c['allocations'])
            record.append(d)
        f=next((c for c in candidates if c['label']=='F'),None)
        return selected['allocations'],dict(candidates=record,selected=selected['label'],horizon=HORIZON,
            phi=selected['score']['phi'],relative_to_F=None if f is None else selected['score']['phi']-f['score']['phi'],
            reason='MAX_PHI_THEN_DELAY_THEN_GPU_CHANGES_THEN_F_K_R',allocator=self.allocator.stats(),gpu_dp_checks=self.dp_checks,
            candidate_seconds=time.perf_counter()-began,mapping_scoring_seconds=self.mapping_seconds)
