import unittest
from capra.upstream import ROOT
from capra.contracts import Node,JobGpuPlan,Allocation
from capra.response_v2 import V2Responses
from capra.node_allocator import NodeAllocator

def plan(items,node='rtx:0'):
    return {k:JobGpuPlan(k,'rtx',g,node,1,0) for k,g in items.items()}

class PairedFixture:
    def __init__(self,fn,axes=(1,2,3)):
        self.fn=fn;self.data={'cpu_axis':list(axes),'ram_axis':list(axes)}
    def rho(self,app,g,c,m):return self.fn(c,m)
    def legal(self,g,c,m,n):return min(self.data['cpu_axis'])<=c<=min(max(self.data['cpu_axis']),n.cpu) and min(self.data['ram_axis'])<=m<=min(max(self.data['ram_axis']),n.ram)

class AllocatorMechanisms(unittest.TestCase):
    def setUp(self):
        self.r=V2Responses(ROOT/'data/responses.json');self.n=Node('rtx:0','rtx',8,24,500)

    def test_intermediate_cpu_points_and_locked_peer(self):
        p=plan({'first':2,'second':1});apps={'first':'cifar10','second':'cifar10'}
        held=Allocation(self.n.id,'rtx',2,18,125,self.r.rho('cifar10',2,18,125))
        s=NodeAllocator(p,[self.n],apps,self.r,{'first':held},{'first':held})
        a,meta=s.solve(self.n.id,p)
        self.assertEqual(a['first'],held);self.assertEqual(a['second'].cpu,6)
        self.assertAlmostEqual(a['second'].rho,1.75)
        p=plan({'c':4,'d':2});apps={'c':'cifar10','d':'deepspeech2'}
        d=Allocation(self.n.id,'rtx',2,6,125,1)
        s=NodeAllocator(p,[self.n],apps,self.r,{'d':d},{'d':d})
        a,meta=s.solve(self.n.id,p)
        self.assertEqual(a['c'].cpu,18);self.assertAlmostEqual(a['c'].rho,1.415)
        self.assertLessEqual(meta['upgrades'],meta['upgrade_bound'])

    def test_bert_reclaims_and_current_vector_is_not_permanent(self):
        p=plan({'b0':1,'b1':1,'c':2});apps={'b0':'bert','b1':'bert','c':'cifar10'}
        cur={k:Allocation(self.n.id,'rtx',q.gpus,3*q.gpus,62.5*q.gpus,1) for k,q in p.items()}
        s=NodeAllocator(p,[self.n],apps,self.r,cur,{})
        a,meta=s.solve(self.n.id,p)
        self.assertEqual((a['b0'].cpu,a['b1'].cpu),(1,1));self.assertEqual(a['c'].cpu,18)
        self.assertAlmostEqual(a['c'].rho,2.4)
        self.assertEqual(s.solve(self.n.id,p)[0],a);self.assertEqual(s.cache_hits,1)

    def test_coupled_reclaim_is_one_legal_pair(self):
        n=Node('rtx:0','rtx',2,6,6);p=plan({'x':1})
        r=PairedFixture(lambda c,m:min(1,(c+m)/4))
        a,_=NodeAllocator(p,[n],{'x':'fixture'},r,{},{}).solve(n.id,p)
        self.assertGreaterEqual(a['x'].rho,1);self.assertGreaterEqual(a['x'].cpu+a['x'].ram,4)
        self.assertNotEqual((a['x'].cpu,a['x'].ram),(1,1))

    def test_joint_upgrade_not_missed(self):
        n=Node('rtx:0','rtx',2,2,2);p=plan({'x':1});r=PairedFixture(min,(1,2))
        a,_=NodeAllocator(p,[n],{'x':'fixture'},r,{},{}).solve(n.id,p)
        self.assertEqual((a['x'].cpu,a['x'].ram,a['x'].rho),(2,2,2))

    def test_query_matches_v1_and_no_lower_clamp_credit(self):
        from capra.response import Responses
        old=Responses(ROOT/'data/responses.json')
        for app in ('cifar10','bert','deepspeech2'):
            for g in (1,2,4):
                for c,m in ((3*g,62.5*g),(4.5*g,70*g),(2.2*g,40*g)):
                    self.assertAlmostEqual(self.r.rho(app,g,c,m),old.rho(app,g,c,m),places=9)
        self.assertFalse(self.r.legal(2,1,20,self.n))
