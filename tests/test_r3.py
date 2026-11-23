import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from capra.smart_r3 import SmartPolicy,SignedCapacity
from capra.upstream import SiaPolicy
from capra.contracts import Node,JobGpuPlan,Allocation
from capra.response_v2 import V2Responses
from capra.placement_r3 import create_placement
from capra.node_allocator import NodeAllocator
from capra.ram_slack import RepairAllocator
from capra.audit_smart_r3 import check_round,check_start
ROOT=Path(__file__).resolve().parents[1]
class SmartTests(unittest.TestCase):
    def policy(self):return SmartPolicy(project_throughputs=True,sched_interval=60)
    def test_sort_and_stable_ties(self):
        p=self.policy();a={'small':(1,1),'largeA':(1,2),'largeB':(1,2),'other':(1,1)}
        out=p.alloc_to_placement('rtx',a,{},np.array([4,4],dtype=np.uint32))
        self.assertEqual(list(out),['largeA','largeB','small','other'])
        self.assertEqual(out['largeA'],[0,0]);self.assertEqual(out['largeB'],[0,0])
    def test_preserve_change_new_full_fragment_repack(self):
        p=self.policy();prev={'a':('rtx',[0,0]),'b':('rtx',[1,1])}
        a={'a':(1,2),'b':(1,2),'full':(1,4)}
        out=p.alloc_to_placement('rtx',a,prev,[4,4])
        self.assertEqual(len(out['full']),4);self.assertTrue(p.smart_records[-1]['evicted'])
        self.assertEqual(sum(map(len,out.values())),8)
        p.alloc_to_placement('rtx',{'a':(1,1),'new':(1,2)},prev,[4,4])
        self.assertNotIn('a',p.smart_records[-1]['preservable'])
        out=p.alloc_to_placement('rtx',{'a':(1,2),'b':(1,2),'new':(1,4)},prev,[4,4])
        self.assertEqual(len(set(out['new'])),1)
    def test_empty_zero_signed_and_illegal_raw(self):
        p=self.policy();self.assertEqual(p.alloc_to_placement('rtx',{}, {},[4,4]),{})
        self.assertEqual(p.alloc_to_placement('rtx',{'z':(0,0)}, {},[4,4]),{'z':[]})
        x=SignedCapacity(np.array([4,4],dtype=np.uint32))
        with self.assertRaises(AssertionError):x[0]-=5
        with self.assertRaises(AssertionError):x[0]+=1
        with patch.object(p,'alloc_to_placement_smart',return_value={'a':[0,0,0,0,0]}):
            with self.assertRaises(AssertionError):p.alloc_to_placement('rtx',{'a':(1,2)}, {},[4,4])
        with self.assertRaises(AssertionError):p.alloc_to_placement('rtx',{'a':(1,2),'b':(1,2)}, {'a':('rtx',[0,0]),'b':('rtx',[0,0])},[2,2])
    def test_fast_smart_same_fixed_gpu_config(self):
        a={'a':(1,2),'b':(1,1),'c':(1,1)};prev={'a':('rtx',[1,1])}
        x=SiaPolicy(project_throughputs=True,sched_interval=60).alloc_to_placement_fast('rtx',a,prev,np.array([4,4],dtype=np.uint32))
        y=self.policy().alloc_to_placement('rtx',a,prev,[4,4])
        self.assertEqual({k:len(v) for k,v in x.items()},{k:len(v) for k,v in y.items()})
        self.assertEqual(y['a'],[1,1]);self.assertNotEqual(x['a'],y['a'])
    def test_smart_quota_isolation_and_name(self):
        n=[Node('rtx:0','rtx',8,24,500),Node('rtx:1','rtx',8,24,500)]
        plan={'a':JobGpuPlan('a','rtx',2,'rtx:0',1,0)};apps={'a':'cifar10'}
        r=V2Responses(ROOT/'data/scenarios_r1/responses_original.json');costs={'cifar10':{'rtx':50}}
        p=create_placement(plan,n,apps,r,{}, {},{},costs,set(),method='SIA-SMART-P',allocator_mode='none')
        forbidden=AssertionError('FORBIDDEN')
        with patch.object(p,'fixed',side_effect=forbidden),patch.object(p,'retained',side_effect=forbidden),patch.object(p,'reordered',side_effect=forbidden),patch.object(NodeAllocator,'solve',side_effect=forbidden),patch.object(NodeAllocator,'layout',side_effect=forbidden),patch.object(NodeAllocator,'pairs',side_effect=forbidden),patch.object(NodeAllocator,'optimize',side_effect=forbidden),patch.object(RepairAllocator,'solve',side_effect=forbidden),patch.object(r,'preferred',side_effect=forbidden):
            out,s=p.select('SIA-SMART-P')
        self.assertEqual(out['a'].cpu,6);self.assertEqual(out['a'].ram,125);self.assertEqual(s['relative_to_F'],None)
        self.assertEqual([x['label'] for x in s['candidates']],['P'])
    def fixture(self):
        nodes={'rtx:0':dict(id='rtx:0',gpu_type='rtx',gpus=4,cpu=12,ram=250),'rtx:1':dict(id='rtx:1',gpu_type='rtx',gpus=4,cpu=12,ram=250)}
        raw={'a':dict(gpu_type='rtx',gpus=2,node='rtx:1')};repaired={'a':dict(raw['a'],node='rtx:0')}
        c=dict(cluster='rtx',gpu_allocations={'a':dict(nodes=1,gpus=2)},raw_smart_plan={'a':[1,1]},initial_capacity=[4,4],remaining_capacity=[4,2],sort_fix=True,signed_capacity=True,raw_valid=True,retained=[],preservable=[],evicted=[])
        r=dict(gpu_stage=dict(placement_engine='sia_smart_adapted_v1',raw_valid=True,mip_calls=1,solver_status='optimal',smart_records=[c],same_mip_physical_witness=[dict(job='a',node='rtx:0',gpu_type='rtx',gpus=2,config_index=0)],repairs=[dict(reason='SHARED_PHYSICAL_LOCK_REPAIR',before={'a':'rtx:1'},after={'a':'rtx:0'})]),raw_sia_plan=raw,lock_repaired_gpu_plan=repaired,locks={'a':dict(node='rtx:0',cpu=6,ram=125)})
        return r,dict(method='SIA-SMART-P',placement_engine='sia_smart_adapted_v1'),nodes
    def test_independent_witness_accept_reject(self):
        r,s,n=self.fixture();check_round(r,s,n)
        for change in ('engine','missing_repair','gpu','witness'):
            x=copy.deepcopy(r)
            if change=='engine':x['gpu_stage']['placement_engine']='sia_fast_original'
            if change=='missing_repair':x['gpu_stage']['repairs']=[]
            if change=='gpu':x['raw_sia_plan']['a']['gpus']=4
            if change=='witness':x['gpu_stage']['same_mip_physical_witness'][0]['node']='rtx:1'
            with self.assertRaises(AssertionError):check_round(x,s,n)
    def test_locked_remaining_no_double_charge(self):
        from capra.costs import transition
        a=Allocation('rtx:0','rtx',2,6,125,1)
        t=transition('a',a,{'a':a},{'a':a},{'a':87},{'a':'bert'},{'bert':{'rtx':120}},{'a'})
        self.assertEqual(t['existing_remaining'],87);self.assertEqual(t['new_cost'],0)
if __name__=='__main__':unittest.main()
