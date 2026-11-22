"""At most two complete starts, frozen finite pairs, paired reclaim and upgrades."""
import math,time
from .contracts import Allocation,validate
from .tune import proportional

EPS=1e-9
CAP_EPS=1e-7

class NodeAllocator:
    def __init__(self,plan,nodes,apps,response,current,locks):
        self.plan=plan;self.nodes={n.id:n for n in nodes};self.apps=apps;self.response=response
        self.current=current;self.locks=locks;self.cache={};self.calls=0;self.cache_hits=0
        self.generated_pairs=0;self.generation_seconds=0.0;self.upgrades=0

    def compatible(self,k,n):
        a=self.current.get(k);p=self.plan[k]
        return a is not None and (a.gpu_type,a.gpus)==(p.gpu_type,p.gpus) and self.response.legal(p.gpus,a.cpu,a.ram,n)

    def baseline(self,node,ids):
        out={}
        for k in ids:
            if k in self.locks:
                assert self.locks[k].node==node.id,'LOCK_LAYOUT'
                out[k]=self.locks[k]
            else:out[k]=proportional(self.plan[k],node,self.response,self.apps[k])
        validate({k:self.plan[k] for k in ids},out,[node],{k:self.locks[k] for k in ids if k in self.locks})
        return out

    def pairs(self,k,node,base):
        p=self.plan[k];g=p.gpus;r=self.response
        other_c=sum(a.cpu for j,a in base.items() if j!=k);other_m=sum(a.ram for j,a in base.items() if j!=k)
        boundary=(node.cpu-other_c,node.ram-other_m)
        cs=set(float(c*g) for c in r.data['cpu_axis'])
        cs.update(float(c) for c in range(math.ceil(r.data['cpu_axis'][0]*g),math.floor(node.cpu)+1))
        ms=set(float(m*g) for m in r.data['ram_axis'])
        cs.update((base[k].cpu,boundary[0]));ms.update((base[k].ram,boundary[1]))
        if self.compatible(k,node):cs.add(self.current[k].cpu);ms.add(self.current[k].ram)
        raw=[(base[k].cpu,base[k].ram)]
        raw.extend((c,m) for c in sorted(cs) for m in sorted(ms) if r.legal(g,c,m,node))
        unique={}
        for c,m in raw:
            if r.legal(g,c,m,node):unique.setdefault((round(c,8),round(m,8)),(c,m))
        points=sorted(unique.values())
        values=r.rhos(self.apps[k],g,points) if hasattr(r,'rhos') else [r.rho(self.apps[k],g,*x) for x in points]
        floor=proportional(p,node,r,self.apps[k]).rho
        result=[Allocation(node.id,p.gpu_type,g,c,m,rho) for (c,m),rho in zip(points,values) if rho>=floor-EPS]
        assert result,'NO_PROPORTIONAL_FLOOR_POINT'
        return tuple(result)

    @staticmethod
    def fits(node,alloc):
        return all(sum(getattr(a,k) for a in alloc.values())<=getattr(node,k)+CAP_EPS for k in ('gpus','cpu','ram'))

    def optimize(self,node,initial,pools):
        out=dict(initial);reclaims=0;steps=0;dominance=0
        norm=lambda a:a.cpu/node.cpu+a.ram/node.ram
        for k in sorted(pools):
            a=out[k]
            options=[b for b in pools[k] if b.cpu<=a.cpu+EPS and b.ram<=a.ram+EPS and b.rho>=a.rho-EPS]
            b=min(options,key=lambda b:(round(norm(b),12),-round(b.rho,12),b.cpu,b.ram))
            reclaims+=b!=a;out[k]=b
        limit=sum(len(v)-1 for v in pools.values())
        while True:
            chosen=None;bestkey=None;dom=False
            # Dominating, no-increase improvements are a separate finite phase.
            for k,pool in sorted(pools.items()):
                a=out[k]
                for b in pool:
                    if b.rho>a.rho+EPS and b.cpu<=a.cpu+EPS and b.ram<=a.ram+EPS:
                        key=(-round(b.rho-a.rho,12),round(norm(b),12),k,b.cpu,b.ram)
                        if bestkey is None or key<bestkey:bestkey=key;chosen=(k,b);dom=True
            if chosen is None:
                used_c=sum(a.cpu for a in out.values());used_m=sum(a.ram for a in out.values())
                for k,pool in sorted(pools.items()):
                    a=out[k]
                    for b in pool:
                        gain=b.rho-a.rho
                        if gain<=EPS or used_c+b.cpu-a.cpu>node.cpu+CAP_EPS or used_m+b.ram-a.ram>node.ram+CAP_EPS:continue
                        denominator=max(0,b.cpu-a.cpu)/node.cpu+max(0,b.ram-a.ram)/node.ram
                        assert denominator>EPS,'ZERO_DENOMINATOR_NOT_DOMINANCE'
                        key=(-round(gain/denominator,12),-round(gain,12),k,b.cpu,b.ram)
                        if bestkey is None or key<bestkey:bestkey=key;chosen=(k,b)
            if chosen is None:break
            k,b=chosen;assert b.rho>out[k].rho+EPS
            out[k]=b;steps+=1;dominance+=dom
            assert steps<=limit,'FINITE_UPGRADE_BOUND'
            assert self.fits(node,out)
        return out,dict(reclaims=reclaims,upgrades=steps,dominance_steps=dominance,upgrade_bound=limit)

    def solve(self,node_id,ids):
        self.calls+=1;ids=tuple(sorted(ids));key=(node_id,ids)
        if key in self.cache:
            self.cache_hits+=1
            a,meta=self.cache[key];return dict(a),meta
        n=self.nodes[node_id];base=self.baseline(n,ids)
        began=time.perf_counter()
        pools={k:self.pairs(k,n,base) for k in ids if k not in self.locks}
        gen=time.perf_counter()-began;self.generation_seconds+=gen
        count=sum(len(x) for x in pools.values());self.generated_pairs+=count
        starts=[('proportional',base)]
        cur=dict(base)
        for k in pools:
            if self.compatible(k,n):
                a=self.current[k];rho=self.response.rho(self.apps[k],a.gpus,a.cpu,a.ram)
                if rho>=base[k].rho-EPS:cur[k]=Allocation(n.id,a.gpu_type,a.gpus,a.cpu,a.ram,rho)
        if cur!=base and self.fits(n,cur):starts.append(('compatible_current',cur))
        solved=[]
        for label,start in starts:
            a,m=self.optimize(n,start,pools);self.upgrades+=m['upgrades']
            total=sum(x.rho for x in a.values());resource=sum(x.cpu/n.cpu+x.ram/n.ram for x in a.values())
            solved.append(((-round(total,10),round(resource,12),tuple((k,x.cpu,x.ram) for k,x in sorted(a.items())),label),a,m))
        _,out,detail=min(solved,key=lambda v:v[0])
        validate({k:self.plan[k] for k in ids},out,[n],{k:self.locks[k] for k in ids if k in self.locks})
        for k,a in out.items():
            if k not in self.locks:assert a.rho>=base[k].rho-EPS and self.response.legal(a.gpus,a.cpu,a.ram,n)
        meta=dict(candidate_pairs={k:len(v) for k,v in pools.items()},generation_seconds=gen,initial_vectors=len(starts),selected_start=min(solved,key=lambda v:v[0])[0][3],**detail)
        self.cache[key]=(dict(out),meta)
        return out,meta

    def layout(self,layout):
        assert set(layout)==set(self.plan),'INCOMPLETE_LAYOUT'
        out={};metadata={}
        for nid in sorted(self.nodes):
            ids=[k for k,v in layout.items() if v==nid]
            if ids:
                a,m=self.solve(nid,ids);out.update(a);metadata[nid]=m
        validate(self.plan,out,list(self.nodes.values()),self.locks)
        return out,metadata

    def stats(self):return dict(node_calls=self.calls,node_cache_hits=self.cache_hits,generated_pairs=self.generated_pairs,generation_seconds=self.generation_seconds,upgrades=self.upgrades)
