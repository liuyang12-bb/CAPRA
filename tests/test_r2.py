import json,math,unittest
from pathlib import Path
from unittest.mock import patch
from dataclasses import replace
from capra.contracts import Node,JobGpuPlan,Allocation,serialized
from capra.response_v2 import V2Responses
from capra.response import Responses
from capra.placement import CandidateInfeasible
from capra.placement_r2 import PlacementR2
from capra.node_allocator import NodeAllocator
from capra.ram_slack import repair,RepairAllocator
from capra.audit_ram_r2 import verify_trace
ROOT=Path(__file__).resolve().parents[1]

class R2Contracts(unittest.TestCase):
    def setUp(self):
        self.n=Node('rtx:0','rtx',8,24,500);self.r=V2Responses(ROOT/'data/scenarios_r1/responses_cm.json')
        self.p={k:JobGpuPlan(k,'rtx',4,self.n.id,1,0) for k in ('C','M')};self.apps={'C':'cifar10','M':'deepspeech2'}
    def test_known_ram_gap_and_legacy_unchanged(self):
        legacy,_=NodeAllocator(self.p,[self.n],self.apps,self.r,{},{}).solve(self.n.id,self.p)
        self.assertEqual(legacy['M'].ram,250)
        out,t=repair(self.n,legacy,self.apps,self.r,{})
        self.assertAlmostEqual(out['M'].ram,416.68);self.assertAlmostEqual(out['M'].rho,1.50004)
        self.assertEqual(out['C'],legacy['C']);self.assertEqual(t['ram_steps'],1)
        verify_trace(t,vars(self.n),self.apps,Responses(ROOT/'data/scenarios_r1/responses_cm.json'),{})
    def test_three_job_certificate(self):
        p={k:JobGpuPlan(k,'rtx',g,self.n.id,1,0) for k,g in [('C',4),('M',2),('N',2)]};apps={'C':'cifar10','M':'deepspeech2','N':'bert'}
        out,_=RepairAllocator(p,[self.n],apps,self.r,{},{}).solve(self.n.id,p)
        self.assertGreaterEqual(out['C'].rho,1);self.assertGreaterEqual(out['M'].rho,1);self.assertEqual(out['N'].rho,1)
        self.assertLessEqual(math.fsum(a.ram for a in out.values()),500)
    def test_flat_full_saturated_locked_strict_noop(self):
        for app,ram in [('cifar10',250),('deepspeech2',500),('deepspeech2',125)]:
            cpu=6 if app=='cifar10' else 2
            a=Allocation(self.n.id,'rtx',2,cpu,ram,self.r.rho(app,2,cpu,ram));initial={'x':a}
            locks=initial if ram==125 else {}
            out,t=repair(self.n,initial,{'x':app},self.r,locks)
            self.assertEqual(out,initial);self.assertEqual(t['ram_steps'],0)
        a=Allocation(self.n.id,'rtx',8,8,500,1)
        self.assertEqual(repair(self.n,{'x':a},{'x':'deepspeech2'},self.r,{})[0],{'x':a})
    def test_competing_M_deterministic_capacity_and_bound(self):
        initial={k:Allocation(self.n.id,'rtx',2,2,125,1) for k in ('a','b')};apps={k:'deepspeech2' for k in initial}
        a,t=repair(self.n,initial,apps,self.r,{})
        b,u=repair(self.n,dict(reversed(list(initial.items()))),apps,self.r,{})
        self.assertEqual(a,b);self.assertEqual(t['updates'],u['updates']);self.assertLessEqual(t['ram_steps'],t['ram_step_bound'])
        self.assertLessEqual(math.fsum(x.ram for x in a.values()),500)
        self.assertEqual(t['updates'][0]['selected']['job'],'a')
    def test_floating_capacity_and_cache_isolation(self):
        n=replace(self.n,ram=500.00000000000006)
        initial={'C':Allocation(n.id,'rtx',4,20,83.32,1.53),'M':Allocation(n.id,'rtx',4,4,250,1)}
        out,t=repair(n,initial,self.apps,self.r,{})
        self.assertLessEqual(math.fsum(a.ram for a in out.values()),n.ram)
        solver=RepairAllocator(self.p,[self.n],self.apps,self.r,{},{});a,m=solver.solve(self.n.id,self.p);b,q=solver.solve(self.n.id,self.p)
        self.assertEqual(a,b);self.assertEqual(solver.stats()['ram_calls'],1);self.assertEqual(solver.stats()['ram_cache_hits'],1)
        self.assertEqual(solver.stats()['upgrades'],solver.base.upgrades)
    def test_FK_call_isolation_and_exact_proportion(self):
        nodes=[self.n,replace(self.n,id='rtx:1')];costs={'cifar10':{'rtx':50},'deepspeech2':{'rtx':25}}
        p={'C':replace(self.p['C'],gpus=2),'M':replace(self.p['M'],gpus=2,node='rtx:1')}
        def make(method,mode):return PlacementR2(p,nodes,self.apps,self.r,{}, {},{},costs,set(),method=method,allocator_mode=mode)
        forbidden=AssertionError('FORBIDDEN_CALL')
        for failed in (False,True):
            obj=make('SIA-P-K','none')
            with patch.object(obj,'reordered',side_effect=forbidden),patch.object(NodeAllocator,'solve',side_effect=forbidden),patch.object(NodeAllocator,'layout',side_effect=forbidden),patch.object(NodeAllocator,'pairs',side_effect=forbidden),patch.object(NodeAllocator,'optimize',side_effect=forbidden),patch.object(RepairAllocator,'solve',side_effect=forbidden):
                if failed:
                    with patch.object(obj,'retained',side_effect=CandidateInfeasible('ISOLATION_FIXTURE')):a,meta=obj.select()
                else:a,meta=obj.select()
                self.assertEqual(meta['r_calls'],0);self.assertEqual([c['label'] for c in meta['candidates']],['F','K'])
                for c in meta['candidates']:
                    if c['feasible']:
                        for x in c['allocations'].values():self.assertEqual((x['cpu'],x['ram']),(3*x['gpus'],62.5*x['gpus']))
            obj=make('CAPRA-FK','legacy')
            with patch.object(obj,'reordered',side_effect=forbidden):
                if failed:
                    with patch.object(obj,'retained',side_effect=CandidateInfeasible('ISOLATION_FIXTURE')):a,meta=obj.select()
                else:a,meta=obj.select()
                self.assertEqual(meta['r_calls'],0)
if __name__=='__main__':unittest.main()
