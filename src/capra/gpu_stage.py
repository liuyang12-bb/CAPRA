"""Thin interface around the official Sia goodput MIP, not a new GPU objective."""
from copy import copy
import numpy as np
import cvxpy as cp
from .upstream import SiaPolicy, JobInfo, NodeInfo, APPLICATIONS
from .contracts import JobGpuPlan, validate
from .tune import proportional


class GpuStage:
    def __init__(self,nodes,interval):
        self.nodes=nodes
        self.types=list(dict.fromkeys(n.gpu_type for n in nodes))
        self.gpn={t:next(n.gpus for n in nodes if n.gpu_type==t) for t in self.types}
        self.count={t:sum(n.gpu_type==t for n in nodes) for t in self.types}
        self.policy=SiaPolicy(project_throughputs=True,sched_interval=interval)
        self.policy.populate_valid_configs(self.count,self.gpn,{t:1 for t in self.types})
        self.policy.capra_constraints=self.lock_constraints
        self.locks={}
        self.placements=[]
        self.xputs={}
        for app in ('cifar10','imagenet','bert','deepspeech2'):
            self.xputs[app]={}
            for t in self.types:
                df=APPLICATIONS[t][app].placements
                df=df[df.num_replicas==1]
                self.xputs[app][t]=float(df.local_bsz.max()/df.step_time.max())

    def info(self,job,now):
        maxrep={t:min(max(2*job.max_profiled_replicas(t),1),self.gpn[t],job.applications[t].max_batch_size//job.applications[t].min_local_bsz) for t in self.types}
        x=JobInfo({'nvidia.com/gpu':1},{t:job.get_speedup_fn(t) for t in self.types},job.submission_time,job.attained_service,{t:0 for t in self.types},maxrep)
        x.used_gpu_seconds=job.used_gpu_seconds; x.wasted_gpu_seconds=job.wasted_gpu_seconds
        x.category=None; x.num_restarts=job.num_restarts or 0; x.num_migrations=job.num_migrations or 0
        x.age=now-job.submission_time
        v=self.xputs[job.app_name]
        x.cluster_throughputs=v
        x.cluster_throughput_ratios={t:{u:v[t]/v[u] for u in self.types if u!=t} for t in self.types}
        x.scaling_underway=job.name in self.locks
        x.scale_unit={t:1 for t in self.types}
        return x

    def lock_constraints(self,X,names):
        self.placements=[]
        if not self.locks:
            return []
        # Shared conservative physical-feasibility repair domain: exact locked quotas,
        # proportional quotas otherwise. Objective and X choices are still official Sia.
        # This prevents forcing unexecutable aggregate GPU plans while locks borrow aux.
        constraints=[]
        for t in self.types:
            idx=[k for k,c in self.policy.idx_to_config_map.items() if c[0]==t]
            g=np.array([self.policy.idx_to_config_map[k][2] for k in idx],float)
            typed=[n for n in self.nodes if n.gpu_type==t]
            Y=[cp.Variable((len(names),len(idx)),boolean=True) for _ in typed]
            constraints.append(sum(Y)==X[:,idx])
            for n,y in zip(typed,Y):
                constraints.append(cp.sum(cp.multiply(y,g))<=n.gpus)
                c=np.tile(g*n.cpu/n.gpus,(len(names),1))
                m=np.tile(g*n.ram/n.gpus,(len(names),1))
                for j,name in enumerate(names):
                    if name in self.locks:
                        a=self.locks[name]
                        if a.node!=n.id:
                            constraints.append(y[j,:]==0)
                        else:
                            c[j,:]=a.cpu; m[j,:]=a.ram
                constraints.extend([cp.sum(cp.multiply(y,c))<=n.cpu,cp.sum(cp.multiply(y,m))<=n.ram])
                self.placements.append((n,idx,g,names,y))
        return constraints

    def choose(self,jobs,now,current,locks,response):
        self.locks=dict(locks)
        active={j.name:j for j in jobs if j.submission_time<=now and j.completion_time is None}
        if not active:
            return {},dict(repairs=[],solver_status='NO_JOBS')
        info={k:self.info(j,now) for k,j in active.items()}
        ni={t:{i:NodeInfo({'nvidia.com/gpu':n.gpus},False) for i,n in enumerate(n for n in self.nodes if n.gpu_type==t)} for t in self.types}
        prev={k:(a.gpu_type,[int(a.node.rsplit(':',1)[1])]*a.gpus) for k,a in current.items() if k in active}
        original=self.policy.optimize(info,ni,prev)
        plan={}
        for name,(t,ids) in original.items():
            if not ids:
                continue
            assert len(set(ids))==1,'SIA_OUTSIDE_SINGLE_NODE_DOMAIN'
            p=copy(active[name]);p.current_cluster=t;p.placement=(len(ids),);p.update_local_bsz(p.placement)
            plan[name]=JobGpuPlan(name,t,len(ids),f'{t}:{ids[0]}',int(p.atomic_bsz),int(p.accum_steps))
        original_plan=dict(plan)
        apps={k:active[k].app_name for k in plan}
        node_map={n.id:n for n in self.nodes}
        def baseline():return {k:(locks[k] if k in locks else proportional(p,node_map[p.node],response,apps[k])) for k,p in plan.items()}
        repairs=[]
        try:
            # Also require the reference location to match a held physical location.
            assert all(plan[k].node==a.node for k,a in locks.items())
            validate(plan,baseline(),self.nodes,locks)
        except AssertionError:
            witness={}
            for n,idx,g,names,y in self.placements:
                assert y.value is not None
                for j,k in enumerate(names):
                    for c,gpus in enumerate(g):
                        if y.value[j,c]>0.5:
                            assert k not in witness
                            witness[k]=n.id
            assert set(witness)==set(plan),'NO_COMPLETE_PHYSICAL_WITNESS'
            from dataclasses import replace
            plan={k:replace(p,node=witness[k]) for k,p in plan.items()}
            validate(plan,baseline(),self.nodes,locks)
            repairs.append(dict(reason='SHARED_PHYSICAL_LOCK_REPAIR',before={k:p.node for k,p in original_plan.items()},after=witness))
        return plan,dict(repairs=repairs,solver_status=self.policy.capra_solver_status,solver_objective=float(self.policy.capra_solver_objective),physical_lock_constraints=bool(locks),original_sia_plan={k:dict(gpu_type=p.gpu_type,gpus=p.gpus,node=p.node) for k,p in original_plan.items()})
