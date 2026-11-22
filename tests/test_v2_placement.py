import unittest
from unittest.mock import patch
from dataclasses import replace
from capra.contracts import Node,JobGpuPlan,Allocation
from capra.response_v2 import V2Responses
from capra.upstream import ROOT
from capra.placement import Placement,CandidateInfeasible
from capra.identity import reference

class CandidateMechanisms(unittest.TestCase):
    def setUp(self):
        self.nodes=[Node('rtx:0','rtx',8,24,500),Node('rtx:1','rtx',8,24,500)]
        self.r=V2Responses(ROOT/'data/responses.json')
        self.apps={'b0':'bert','b1':'bert','c0':'cifar10','c1':'cifar10'}
        self.p={k:JobGpuPlan(k,'rtx',4 if k.startswith('b') else 2,'rtx:0' if k.startswith('b') else 'rtx:1',1,0) for k in self.apps}
        self.costs={'bert':{'rtx':120},'cifar10':{'rtx':50}}

    def build(self,current=None,locks=None,remaining=None):
        cur=current or {};locks=locks or {};remaining=remaining or {}
        p,_=reference(self.p,self.nodes,cur,locks,remaining,self.apps,self.costs,set(cur),self.r)
        return Placement(p,self.nodes,self.apps,self.r,cur,locks,remaining,self.costs,set(cur))

    def test_resource_complementarity_and_f_contract(self):
        a=self.build();f=a.fixed()
        fixed,log=self.build().select('CAPRA-Fixed')
        self.assertEqual(fixed,f['allocations'])
        r=a.reordered()
        for n in self.nodes:
            ids=[k for k,v in r['allocations'].items() if v.node==n.id]
            self.assertEqual(len(ids),2)
            self.assertEqual(sorted(self.apps[k] for k in ids),['bert','cifar10'])
        chosen,log=self.build().select('CAPRA')
        self.assertGreaterEqual(log['relative_to_F'],-1e-9)
        self.assertEqual(self.build().select('CAPRA')[0],chosen)
        self.assertLessEqual(len(log['candidates']),3)

    def test_k_r_failure_returns_existing_complete_f(self):
        obj=self.build();f=obj.fixed()['allocations']
        with patch.object(obj,'retained',side_effect=CandidateInfeasible('fixture K unavailable')),patch.object(obj,'reordered',side_effect=CandidateInfeasible('fixture R unavailable')):
            a,log=obj.select('CAPRA')
        self.assertEqual(a,f);self.assertEqual(log['selected'],'F');self.assertEqual(set(a),set(self.p))

    def test_gpu_fragmentation_8_2_2(self):
        p={k:JobGpuPlan(k,'rtx',g,'rtx:0' if k=='z' else 'rtx:1',1,0) for k,g in {'a':2,'b':2,'z':8}.items()}
        obj=Placement(p,self.nodes,{k:'bert' for k in p},self.r,{}, {},{},self.costs,set())
        self.assertFalse(obj.gpu_feasible({'a':'rtx:0','b':'rtx:1'},{'z'}))
        r=obj.reordered()['allocations']
        self.assertNotEqual(r['z'].node,r['a'].node);self.assertEqual(r['a'].node,r['b'].node)

    def test_common_reference_fixed_stability_and_soft_positions(self):
        # No candidate may mutate the immutable actual allocations dictionary.
        cur={k:Allocation(q.node,'rtx',q.gpus,3*q.gpus,62.5*q.gpus,1) for k,q in self.p.items()}
        original=dict(cur);obj=self.build(cur)
        a,log=obj.select('CAPRA');self.assertEqual(cur,original)
        self.assertTrue(any(c['label']=='R' and c['feasible'] for c in log['candidates']))
        f=obj.fixed()['allocations'];self.assertTrue(all(x.node==obj.plan[k].node for k,x in f.items()))
