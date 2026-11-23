"""Exact legacy layout construction with explicit quota strategies and candidate sets."""
import time
from .placement import Placement,CandidateInfeasible,HORIZON
from .contracts import serialized,validate
from .costs import EPS
from .node_allocator import NodeAllocator
from .ram_slack import RepairAllocator
from .tune import proportional
from .methods_r2 import spec

class ProportionalAllocator:
    def __init__(self,plan,nodes,apps,response,current,locks):
        self.plan=plan;self.nodes={n.id:n for n in nodes};self.apps=apps;self.response=response;self.locks=locks
    def baseline(self,node,ids):
        a={k:(self.locks[k] if k in self.locks else proportional(self.plan[k],node,self.response,self.apps[k])) for k in ids}
        for k in ids:
            if k in self.locks:assert self.locks[k].node==node.id,'LOCK_LAYOUT'
        validate({k:self.plan[k] for k in ids},a,[node],{k:self.locks[k] for k in ids if k in self.locks})
        return a
    def layout(self,layout):
        assert set(layout)==set(self.plan);out={}
        for nid in sorted(self.nodes):out.update(self.baseline(self.nodes[nid],[k for k,v in layout.items() if v==nid]))
        validate(self.plan,out,list(self.nodes.values()),self.locks);return out,{}
    def stats(self):return dict(node_calls=0,node_cache_hits=0,generated_pairs=0,generation_seconds=0.,upgrades=0)

class PlacementR2(Placement):
    def __init__(self,*args,method,allocator_mode):
        super().__init__(*args);self.method=method;self.method_spec=spec(method,allocator_mode);self.r_calls=0
        if allocator_mode=='none':self.allocator=ProportionalAllocator(*args[:6])
        elif allocator_mode=='ram_slack_v1':self.allocator=RepairAllocator(*args[:6])
    def reordered(self):
        self.r_calls+=1
        return super().reordered()
    def select(self,method=None):
        method=method or self.method;assert method==self.method
        began=time.perf_counter();candidates=[];timings={label:None for label in ('F','K','R','P')}
        for label in self.method_spec['candidate_labels']:
            started=time.perf_counter()
            try:
                if label=='P':
                    a=self.reserved({k:p.node for k,p in self.plan.items()});c=self.finish('P',a,{})
                    assert all(x.node==self.plan[k].node for k,x in c['allocations'].items())
                else:c={'F':self.fixed,'K':self.retained,'R':self.reordered}[label]()
            except CandidateInfeasible as error:
                assert label in ('K','R');c=dict(label=label,feasible=False,reason=str(error))
            timings[label]=time.perf_counter()-started;candidates.append(c)
        valid=[c for c in candidates if c['feasible']];selected=valid[0]
        for c in valid[1:]:
            a,b=c['score'],selected['score'];better=a['phi']>b['phi']+EPS
            if abs(a['phi']-b['phi'])<=EPS:better=a['total_delay']<b['total_delay']-EPS or (abs(a['total_delay']-b['total_delay'])<=EPS and a['changes']<b['changes'])
            if better:selected=c
        f=next((c for c in valid if c['label']=='F'),None)
        if f is not None:assert selected['score']['phi']+EPS>=f['score']['phi']
        record=[]
        for c in candidates:
            d=dict(c)
            if c['feasible']:d['allocations']=serialized(c['allocations'])
            record.append(d)
        return selected['allocations'],dict(candidates=record,selected=selected['label'],horizon=HORIZON,phi=selected['score']['phi'],
            relative_to_F=None if f is None else selected['score']['phi']-f['score']['phi'],reason='MAX_PHI_THEN_DELAY_THEN_GPU_CHANGES_THEN_F_K_R',
            allocator=self.allocator.stats(),gpu_dp_checks=self.dp_checks,candidate_seconds=time.perf_counter()-began,mapping_scoring_seconds=self.mapping_seconds,
            candidate_timings=timings,r_calls=self.r_calls,r_skipped='R' not in self.method_spec['candidate_labels'],method_spec=self.method_spec)
