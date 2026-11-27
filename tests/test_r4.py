import unittest,copy,sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from capra.contracts import Node,JobGpuPlan,Allocation,serialized
from capra.response_v2 import V2Responses
from capra.response import Responses
from capra.placement_r3 import create_placement as old
from capra.placement_r4 import create_placement as new
from capra.node_allocator import NodeAllocator
from opportunity_r4 import funnel_round
from capra.audit_r3 import score
import importlib.util
sp=importlib.util.spec_from_file_location('dense_generator',ROOT/'data/pressure_r4/generate.py');gen=importlib.util.module_from_spec(sp);sp.loader.exec_module(gen)
def clean(x):
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items() if not k.startswith('r4_') and k not in ('generation_seconds','ram_repair_seconds','candidate_seconds','mapping_scoring_seconds','candidate_timings')}
    if isinstance(x,list):return [clean(v) for v in x]
    return x
class R4Tests(unittest.TestCase):
    def test_exact_decimal_input_and_stable_ties(self):
        rows=[dict(name='x'+str(i),time=str(100+i//2),application='cifar10',num_replicas='1',batch_size='32') for i in range(80)]
        out,m=gen.transform(rows);self.assertEqual(out[2]['time'],'100.5');self.assertEqual(out[3]['time'],'100.5')
        self.assertEqual([x['name'] for x in rows],[x['name'] for x in out]);self.assertEqual(len(m),80)
        self.assertTrue(all({k:v for k,v in a.items() if k!='time'}=={k:v for k,v in b.items() if k!='time'} for a,b in zip(rows,out)))
    def test_timing_proxy_semantics_and_FK_R_isolation(self):
        nodes=[Node('rtx:0','rtx',8,24,500),Node('rtx:1','rtx',8,24,500)]
        plan={k:JobGpuPlan(k,'rtx',2,'rtx:'+str(i),1,0) for i,k in enumerate(('b','c'))};apps={'c':'cifar10','b':'bert'};costs={'cifar10':{'rtx':50},'bert':{'rtx':120}}
        for method,mode in [('SIA-SMART-P','none'),('CAPRA-FK','ram_slack_v1'),('CAPRA','ram_slack_v1')]:
            args=(plan,nodes,apps,V2Responses(ROOT/'data/scenarios_r1/responses_cm.json'),{}, {},{},costs,set())
            a,s=old(*args,method=method,allocator_mode=mode).select();p=new(*args,method=method,allocator_mode=mode)
            if method!='CAPRA':
                with patch.object(p,'reordered',side_effect=AssertionError('R_FORBIDDEN')):b,t=p.select()
            else:b,t=p.select()
            self.assertEqual(a,b);self.assertEqual(clean(s),clean(t));self.assertGreaterEqual(t['allocator']['r4_allocator_seconds'],0)
    def fixture(self):
        nodes={f'rtx:{i}':dict(id=f'rtx:{i}',gpu_type='rtx',gpus=8,cpu=24,ram=500) for i in (0,1)}
        apps={'c':'cifar10','b':'bert'};response=Responses(ROOT/'data/scenarios_r1/responses_cm.json');costs={'cifar10':50,'bert':120}
        plan={'c':vars(JobGpuPlan('c','rtx',4,'rtx:0',1,0)),'b':vars(JobGpuPlan('b','rtx',2,'rtx:1',1,0))}
        base={'c':vars(Allocation('rtx:0','rtx',4,12,250,1)),'b':vars(Allocation('rtx:1','rtx',2,6,125,1))}
        alt={'c':vars(Allocation('rtx:0','rtx',4,20,83.32,response.rho('cifar10',4,20,83.32))),'b':vars(Allocation('rtx:0','rtx',2,2,125,1))}
        def candidate(label,a):return dict(label=label,feasible=True,allocations=a,score=score(a,{}, {},{},apps,costs,set()))
        r=dict(round=0,time=0.,plan=plan,locks={},selection=dict(candidates=[candidate('F',base),candidate('K',base),candidate('R',alt)],selected='R'),executions=[dict(job='c',training=10.,allocation=alt['c'])])
        return r,nodes,response,apps
    def test_strict_funnel_full_and_uncovered_protocol(self):
        r,n,p,a=self.fixture();x=funnel_round(r,n,p,a);self.assertTrue(all(x['stages'].values()));self.assertTrue(x['direct_legal_witnesses'])
        r['selection']['candidates']=r['selection']['candidates'][:2];r['selection']['selected']='F';x=funnel_round(r,n,p,a)
        self.assertTrue(x['stages']['E']);self.assertFalse(x['stages']['F']);self.assertIn('R_not_generated_by_protocol',x['nonexclusive_tags'])
    def test_already_colocated_and_locks_do_not_skip_funnel(self):
        r,n,p,a=self.fixture();r['locks']=r['selection']['candidates'][0]['allocations'];x=funnel_round(r,n,p,a)
        self.assertTrue(x['stages']['D']);self.assertFalse(x['stages']['E']);self.assertIn('recovery_lock_blocked',x['nonexclusive_tags'])
        r,n,p,a=self.fixture()
        for c in r['selection']['candidates'][:2]:c['allocations']['b']=dict(c['allocations']['b'],node='rtx:0')
        x=funnel_round(r,n,p,a);self.assertTrue(x['stages']['C']);self.assertFalse(x['stages']['D']);self.assertFalse(x['stages']['I'])
    def test_method_whitelist_and_no_unknown_fallback(self):
        from capra.methods_r4 import spec
        with self.assertRaises(AssertionError):spec('SIA-P-K','none')
        with self.assertRaises(AssertionError):spec('UNKNOWN','ram_slack_v1')
        with self.assertRaises(AssertionError):spec('SIA-SMART-P','ram_slack_v1')
if __name__=='__main__':unittest.main()
