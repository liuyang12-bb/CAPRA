"""Direct physical-node construction; F-only identity, shared unchanged RepairAllocator."""
import hashlib,json,time,copy
from dataclasses import asdict,replace
from .contracts import JobGpuPlan,serialized,validate
from .costs import evaluate,transition,EPS
from .identity import reference
from .ram_slack import RepairAllocator
from .feasibility_direct_r5 import can_finish,check_scope

BASE='ffa953fb9cd12773992559512d85065bbd26b7b2'
VERSION='CAPRA_V2_DIRECT_R5'
METHOD='CAPRA-Direct'
FIELDS=('name','gpu_type','gpus','nodes','atomic_bsz','accum_steps')
H=180.

def gpu_contract(plan):return {k:{f:getattr(p,f) for f in FIELDS} for k,p in sorted(plan.items())}
def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def better_node(a,b):
    if a['delta']>b['delta']+EPS:return True
    if abs(a['delta']-b['delta'])>EPS:return False
    if a['inserted_new_cost']<b['inserted_new_cost']-EPS:return True
    if abs(a['inserted_new_cost']-b['inserted_new_cost'])>EPS:return False
    return (not a['keeps_current_node'],a['node'])<(not b['keeps_current_node'],b['node'])

def better_complete(a,b):
    if a['phi']>b['phi']+EPS:return True
    if abs(a['phi']-b['phi'])>EPS:return False
    return a['total_delay']<b['total_delay']-EPS or (abs(a['total_delay']-b['total_delay'])<=EPS and a['changes']<b['changes'])

class PlacementBudget(Exception):pass

class DirectPlacement:
    def __init__(self,witness,nodes,apps,response,current,locks,remaining,costs,started,budget_seconds=5.,clock=time.perf_counter):
        self.witness=dict(witness);self.contract=gpu_contract(witness);self.digest=fingerprint(self.contract)
        self.nodes=sorted(nodes,key=lambda n:n.id);self.nm={n.id:n for n in self.nodes};check_scope(nodes,self.contract)
        self.apps=dict(apps);self.response=response;self.current=dict(current);self.locks=dict(locks);self.remaining=dict(remaining);self.costs=copy.deepcopy(costs);self.started=set(started)
        assert set(locks)<=set(witness) and set(remaining)==set(locks)
        assert all(self.current.get(k)==a and remaining[k]>EPS for k,a in locks.items())
        # No reference node is available to D or to the shared allocator's plan.
        self.plan={k:JobGpuPlan(**p,node='') for k,p in self.contract.items()}
        self.allocator=RepairAllocator(self.plan,self.nodes,self.apps,response,self.current,self.locks)
        self.clock=clock;self.budget=float(budget_seconds);assert self.budget>=0
        self.trace=dict(contract=self.contract,contract_fingerprint=self.digest,contract_checks=[],
                        f_reference=None,allocation_traces=[],solve_requests=[],initial_check=None,ordering=[],order=None,steps=[],
                        prefix_layout={k:a.node for k,a in sorted(locks.items())},prefix_trace_ids={},D_status='NOT_STARTED',
                        timing=dict(f_reference=0.,f_quota=0.,D=0.,completion_checks_nested=0.,allocator_nested=0.,scoring_nested=0.),
                        counts=dict(dp_checks=0,preferred_queries=0,budget_checks=0),identity_scope='F_ONLY_REFERENCE; D_PHYSICAL_IDS_UNCHANGED')
        self.trace_index={};self.vectors={};self.initial_snapshot=self.state_snapshot()

    def state_snapshot(self):
        return fingerprint(dict(witness=serialized(self.witness),current=serialized(self.current),locks=serialized(self.locks),remaining=self.remaining,started=sorted(self.started),nodes=[asdict(n) for n in self.nodes],apps=self.apps,costs=self.costs,response=self.response.data))

    def unchanged(self,where):
        assert gpu_contract(self.witness)==self.contract and fingerprint(self.contract)==self.digest,'GPU_CONTRACT_CHANGED'
        assert self.state_snapshot()==self.initial_snapshot,'INPUT_STATE_CHANGED'
        self.trace['contract_checks'].append(dict(where=where,fingerprint=self.digest))

    def budget_check(self):
        self.trace['counts']['budget_checks']+=1
        if self.clock()-self.began>=self.budget:raise PlacementBudget()

    def check(self,layout,remaining):
        before=self.clock();result=can_finish(self.contract,self.nodes,self.apps,self.response,self.locks,layout,remaining)
        self.trace['timing']['completion_checks_nested']+=self.clock()-before;self.trace['counts']['dp_checks']+=1
        return result

    def check_alloc(self,a,complete=False):
        p=self.plan if complete else {k:self.plan[k] for k in a}
        validate(p,a,self.nodes,{k:v for k,v in self.locks.items() if k in a})
        for k,x in a.items():
            n=self.nm[x.node];assert self.response.legal(x.gpus,x.cpu,x.ram,n),'PROFILE_DOMAIN'
            assert abs(x.rho-self.response.rho(self.apps[k],x.gpus,x.cpu,x.ram))<=1e-7,'RHO_MISMATCH'
            if k not in self.locks:
                floor=self.response.rho(self.apps[k],x.gpus,n.cpu*x.gpus/n.gpus,n.ram*x.gpus/n.gpus)
                assert x.rho>=floor-EPS,'PROPORTIONAL_FLOOR'

    def score(self,a):
        before=self.clock();v=evaluate(a,self.current,self.locks,self.remaining,self.apps,self.costs,self.started,H)
        self.trace['timing']['scoring_nested']+=self.clock()-before;return v

    def solve(self,nid,ids,phase):
        key=(nid,tuple(sorted(ids)));warm=key in self.trace_index;began=self.clock()
        a,meta=self.allocator.solve(nid,ids)
        self.trace['timing']['allocator_nested']+=self.clock()-began
        self.check_alloc(a)
        if not warm:
            tid=len(self.trace['allocation_traces']);self.trace_index[key]=tid;self.vectors[tid]=dict(a)
            self.trace['allocation_traces'].append(dict(id=tid,node=nid,jobs=list(key[1]),allocations=serialized(a),score=self.score(a),ram_trace_id=meta['ram_trace_id']))
        tid=self.trace_index[key]
        assert a==self.vectors[tid]
        self.trace['solve_requests'].append(dict(node=nid,jobs=list(key[1]),phase=phase,cache_hit=warm,trace_id=tid))
        return tid

    def prepare_f(self):
        before=self.clock()
        p,meta=reference(dict(self.witness),self.nodes,self.current,self.locks,self.remaining,self.apps,self.costs,self.started,self.response)
        self.trace['timing']['f_reference']=self.clock()-before
        self.trace['f_reference']=dict(input_witness=serialized(self.witness),output_plan=serialized(p),details=meta)
        assert gpu_contract(p)==self.contract
        before=self.clock();a={};refs={}
        for n in self.nodes:
            ids=[k for k,v in p.items() if v.node==n.id]
            if ids:
                tid=self.solve(n.id,ids,'F');refs[n.id]=tid;a.update(self.vectors[tid])
        self.check_alloc(a,True);s=self.score(a);self.trace['timing']['f_quota']=self.clock()-before
        assert all(a[k].node==p[k].node for k in p),'F_CHANGED_REFERENCE'
        return dict(label='F',feasible=True,trace_ids=refs,allocations=serialized(a),score=s),a

    def construct_d(self):
        self.trace['D_status']='CONSTRUCTING';layout=dict(self.trace['prefix_layout']);todo=sorted(set(self.contract)-set(self.locks))
        self.budget_check();initial=self.check(layout,todo);self.trace['initial_check']=initial
        assert initial['feasible'],'INITIAL_CAN_FINISH_CONTRADICTS_VALID_F'
        for n in self.nodes:
            self.budget_check();tid=self.solve(n.id,[k for k,v in layout.items() if v==n.id],'LOCK_INITIAL')
            self.trace['prefix_trace_ids'][n.id]=tid
        ordering=[]
        for k in todo:
            self.budget_check();row=dict(job=k,candidates=[],legal_nodes=[],pressure=None,complete=False);self.trace['ordering'].append(row);pressures=[]
            for n in self.nodes:
                if n.gpu_type!=self.contract[k]['gpu_type']:continue
                self.budget_check();trial=dict(layout);trial[k]=n.id;result=self.check(trial,[j for j in todo if j!=k])
                item=dict(node=n.id,can_finish=result);row['candidates'].append(item)
                if result['feasible']:
                    self.budget_check();c,m=self.response.preferred(self.apps[k],self.contract[k]['gpus'],n);self.trace['counts']['preferred_queries']+=1
                    assert self.response.legal(self.contract[k]['gpus'],c,m,n)
                    pressure=max(0.,c/n.cpu-self.contract[k]['gpus']/n.gpus,m/n.ram-self.contract[k]['gpus']/n.gpus)
                    item.update(preferred_cpu=c,preferred_ram=m,pressure=pressure);row['legal_nodes'].append(n.id);pressures.append(pressure)
            self.budget_check();assert pressures,'EMPTY_INITIAL_A_WITH_VALID_F'
            row.update(pressure=max(pressures),complete=True);ordering.append((len(row['legal_nodes']),-self.contract[k]['gpus'],-round(max(pressures),12),k))
        self.budget_check();order=[x[-1] for x in sorted(ordering)];self.trace['order']=order
        for i,k in enumerate(order):
            self.budget_check();step=dict(job=k,index=i,candidates=[],complete=False,chosen_node=None);self.trace['steps'].append(step);remaining=order[i+1:]
            options=[]
            for n in self.nodes:
                if n.gpu_type!=self.contract[k]['gpu_type']:continue
                self.budget_check();trial=dict(layout);trial[k]=n.id;legal=self.check(trial,remaining)
                option=dict(node=n.id,can_finish=legal);step['candidates'].append(option)
                if not legal['feasible']:continue
                before_id=self.trace['prefix_trace_ids'][n.id];self.budget_check()
                after_id=self.solve(n.id,[j for j,v in trial.items() if v==n.id],'D_AFTER')
                bs=self.trace['allocation_traces'][before_id]['score'];ats=self.trace['allocation_traces'][after_id]['score']
                option.update(before_trace_id=before_id,after_trace_id=after_id,delta=ats['phi']-bs['phi'],inserted_new_cost=ats['jobs'][k]['new_cost'],keeps_current_node=self.current.get(k) is not None and self.current[k].node==n.id)
                options.append(option)
            self.budget_check();assert options,'NO_EXTENSION_AFTER_TRUE_CAN_FINISH'
            chosen=options[0]
            for option in options[1:]:
                if better_node(option,chosen):chosen=option
            layout[k]=chosen['node'];self.trace['prefix_trace_ids'][chosen['node']]=chosen['after_trace_id']
            step.update(complete=True,chosen_node=chosen['node'],choice_rule='DELTA_EPS_NEW_COST_KEEP_CURRENT_NODE_ID')
            self.trace['prefix_layout']=dict(layout)
        self.budget_check();a={}
        for tid in self.trace['prefix_trace_ids'].values():a.update(self.vectors[tid])
        self.check_alloc(a,True);s=self.score(a)
        node_sum=sum(self.trace['allocation_traces'][tid]['score']['phi'] for tid in self.trace['prefix_trace_ids'].values())
        assert abs(s['phi']-node_sum)<=1e-7,'NODE_UTILITY_SUM'
        assert {k:x.node for k,x in a.items()}==layout,'D_POST_IDENTITY_TRANSFORM'
        self.budget_check();self.trace['D_status']='COMPLETE'
        return dict(label='D',feasible=True,trace_ids=dict(self.trace['prefix_trace_ids']),allocations=serialized(a),score=s),a

    def select(self):
        self.began=self.clock();before_hits=self.response.hits;before_misses=self.response.misses
        self.unchanged('BEFORE_F_D');f,fa=self.prepare_f();chosen=f;alloc=fa;dc=None
        d_start=self.clock()
        try:
            if self.clock()-self.began>=self.budget:self.trace['D_status']='D_NOT_STARTED_BUDGET'
            else:dc,da=self.construct_d()
        except PlacementBudget:self.trace['D_status']='D_BUDGET'
        except Exception as error:
            self.trace['D_status']='IMPLEMENTATION_ERROR';error.direct_diagnostic=copy.deepcopy(self.trace);raise
        self.trace['timing']['D']=self.clock()-d_start
        if dc is not None and better_complete(dc['score'],f['score']):chosen=dc;alloc=da
        self.unchanged('AFTER_F_D');self.check_alloc(alloc,True)
        assert chosen['score']['phi']>=f['score']['phi']-EPS
        self.trace['allocator']=self.allocator.stats();M=len(self.contract)-len(self.locks);N=len(self.nodes)
        req=self.trace['solve_requests'];assert len(req)<=2*M+2*N
        assert sum(r['phase']=='D_AFTER' for r in req)<=2*M
        self.trace['counts'].update(solve_requests=len(req),cold_solves=len(self.trace['allocation_traces']),cache_hits=sum(r['cache_hit'] for r in req),response_hits=self.response.hits-before_hits,response_misses=self.response.misses-before_misses,response_queries=self.response.hits+self.response.misses-before_hits-before_misses,solve_request_bound=2*M+2*N,D_after_request_bound=2*M)
        self.trace.update(candidates=[f,dc if dc is not None else dict(label='D',feasible=False,reason=self.trace['D_status'])],selected=chosen['label'],phi=chosen['score']['phi'],relative_to_F=chosen['score']['phi']-f['score']['phi'],reason='D_HIGHER_PHI_DELAY_CHANGES' if chosen['label']=='D' else ('F_COMPLETE_REFERENCE_WINS_OR_TIES' if dc is not None else self.trace['D_status']),horizon=H,budget_seconds=self.budget,candidate_seconds=self.clock()-self.began)
        self.trace['budget_overrun_seconds']=max(0.,self.trace['candidate_seconds']-self.budget)
        return alloc,self.trace
