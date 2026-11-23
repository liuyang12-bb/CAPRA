"""Bounded monotone RAM supplement, only after the original final node solution."""
from dataclasses import replace
import math,time
from .contracts import serialized,validate
from .node_allocator import NodeAllocator
EPS=1e-9

def repair(node,initial,apps,response,locks):
    began=time.perf_counter();out=dict(initial);ids=sorted(out)
    bound=sum(sum(m*out[k].gpus>out[k].ram for m in response.data['ram_axis']) for k in ids if k not in locks)+1
    updates=[];evaluated=0
    def options():
        nonlocal evaluated
        choices=[]
        for k in ids:
            if k in locks:continue
            a=out[k];others=math.fsum(out[j].ram for j in ids if j!=k)
            top=min(a.gpus*max(response.data['ram_axis']),node.ram-others)
            # Never borrow the capacity tolerance, including roundoff at the physical bound.
            for _ in range(4):
                if math.fsum([others,top])<=node.ram:break
                top=math.nextafter(top,-math.inf)
            assert math.fsum([others,top])<=node.ram
            points={}
            for m in [x*a.gpus for x in response.data['ram_axis']]+[top]:
                if m-a.ram<=EPS or m>top or not response.legal(a.gpus,a.cpu,m,node):continue
                key=round(m,8)
                if key not in points or m<points[key]:points[key]=m
            for m in sorted(points.values()):
                evaluated+=1
                rho=response.rho(apps[k],a.gpus,a.cpu,m);gain=rho-a.rho;delta=m-a.ram
                if gain<=EPS:continue
                rank=(-round(gain/(delta/node.ram),12),-round(gain,12),k,m)
                choices.append(dict(job=k,ram=m,rho_before=a.rho,rho_after=rho,delta_rho=gain,delta_ram=delta,
                    physical_upper=top,other_ram=others,rank=list(rank),sources=[x for x,flag in [('axis',any(m==z*a.gpus for z in response.data['ram_axis'])),('physical_upper',m==top)] if flag]))
        return sorted(choices,key=lambda c:tuple(c['rank']))
    while True:
        candidates=options()
        if not candidates:break
        choice=candidates[0];k=choice['job'];before=out[k]
        free_before=node.ram-math.fsum(a.ram for a in out.values())
        out[k]=replace(before,ram=choice['ram'],rho=choice['rho_after'])
        assert math.fsum(out[j].ram for j in ids)<=node.ram,'RAM_PHYSICAL_CAPACITY'
        updates.append(dict(index=len(updates)+1,free_ram_before=free_before,
            candidates=candidates,selected=choice,free_ram_after=node.ram-math.fsum(a.ram for a in out.values())))
        assert len(updates)<=bound,'RAM_FINITE_BOUND'
    for k,a in out.items():
        old=initial[k]
        assert (a.node,a.gpu_type,a.gpus,a.cpu)==(old.node,old.gpu_type,old.gpus,old.cpu)
        assert a.rho>=old.rho-EPS and a.ram>=old.ram
        if k in locks:assert a==old==locks[k]
    trace=dict(node=node.id,initial=serialized(initial),final=serialized(out),ram_steps=len(updates),ram_step_bound=bound,
        ram_candidates=evaluated,ram_repair_seconds=time.perf_counter()-began,updates=updates,terminal_candidates=[],
        added_ram=math.fsum(out[k].ram-initial[k].ram for k in ids))
    return out,trace

class RepairAllocator:
    def __init__(self,*args):
        self.base=NodeAllocator(*args);self.plan=self.base.plan;self.nodes=self.base.nodes;self.apps=self.base.apps
        self.response=self.base.response;self.locks=self.base.locks;self.cache={};self.traces=[];self.requests=0;self.hits=0
    def baseline(self,*args):return self.base.baseline(*args)
    def solve(self,node_id,ids):
        self.requests+=1;ids=tuple(sorted(ids));key=('ram_slack_v1',node_id,ids)
        if key in self.cache:
            self.hits+=1;a,m=self.cache[key];return dict(a),m
        old,meta=self.base.solve(node_id,ids)
        a,trace=repair(self.nodes[node_id],old,self.apps,self.response,self.locks)
        trace['legacy_meta']=meta
        trace['trace_id']=len(self.traces);trace['jobs']=list(ids);self.traces.append(trace)
        meta=dict(meta,ram_trace_id=trace['trace_id']);self.cache[key]=(dict(a),meta)
        return a,meta
    def layout(self,layout):
        assert set(layout)==set(self.plan)
        out={};meta={}
        for nid in sorted(self.nodes):
            ids=[k for k,v in layout.items() if v==nid]
            if ids:
                a,m=self.solve(nid,ids);out.update(a);meta[nid]=m
        validate(self.plan,out,list(self.nodes.values()),self.locks)
        return out,meta
    def stats(self):
        return dict(self.base.stats(),ram_requests=self.requests,ram_cache_hits=self.hits,ram_calls=len(self.traces),
            ram_steps=sum(t['ram_steps'] for t in self.traces),ram_step_bound=sum(t['ram_step_bound'] for t in self.traces),
            ram_candidates=sum(t['ram_candidates'] for t in self.traces),ram_repair_seconds=sum(t['ram_repair_seconds'] for t in self.traces),ram_traces=self.traces)
