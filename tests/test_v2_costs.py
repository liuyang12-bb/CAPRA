import unittest
from dataclasses import replace
from capra.contracts import Allocation,Node,JobGpuPlan
from capra.costs import application_costs,transition,evaluate
from capra.identity import stabilize
from capra.execution import commit_v2
from capra.upstream import APPLICATIONS,Job
from test_contracts import linear_job

class CostsAndIdentity(unittest.TestCase):
    def test_prediction_commit_all_transition_kinds(self):
        nodes=[Node('rtx:0','rtx',4,12,250),Node('rtx:1','rtx',4,12,250)]
        base=Allocation('rtx:0','rtx',2,6,125,1)
        for kind,old,new,seen in [('start',None,base,False),('resume',None,base,True),
            ('migration',base,replace(base,node='rtx:1'),True),('reconfigure',base,replace(base,gpus=1,cpu=3,ram=62.5),True),
            ('aux_update',base,replace(base,cpu=7),True)]:
            j=linear_job('A','rtx:0');j.num_restarts=0 if seen else None
            if old is None:j.placement=();j.current_cluster=None
            cur={} if old is None else {'A':old};apps={'A':'cifar10'};costs=application_costs([j]);started={'A'} if seen else set()
            # Fake fixture batch snapshot follows the same actual Job rule.
            from copy import copy
            cp=copy(j);cp.current_cluster=new.gpu_type;cp.update_local_bsz((new.gpus,))
            p={'A':JobGpuPlan('A',new.gpu_type,new.gpus,new.node,cp.atomic_bsz,cp.accum_steps)}
            e,usage,pred=commit_v2([j],p,{'A':new},nodes,cur,{},0,{},apps,costs,started)
            self.assertEqual(pred['A']['kind'],kind)
            self.assertEqual(e[0]['cost'],0 if kind=='aux_update' else 10)
        j=linear_job('A','rtx:0');j.rescale_time=7
        t=transition('A',base,{'A':base},{'A':base},{'A':7},{'A':'cifar10'},application_costs([j]),{'A'})
        self.assertEqual((t['new_cost'],t['delay']),(0,7))

    def test_swap_cost_lock_and_idempotence(self):
        ns=[Node('rtx:0','rtx',4,12,250),Node('rtx:1','rtx',4,12,250)]
        current={'A':Allocation('rtx:0','rtx',2,6,125,1),'B':Allocation('rtx:1','rtx',2,6,125,1)}
        alt={k:replace(a,node='rtx:1' if a.node=='rtx:0' else 'rtx:0') for k,a in current.items()}
        args=(ns,current,{}, {},{'A':'cifar10','B':'bert'},{'cifar10':{'rtx':50},'bert':{'rtx':120}},{'A','B'})
        out,meta=stabilize(alt,*args)
        self.assertEqual(out,current);self.assertEqual(meta['before_delay'],170);self.assertEqual(meta['after_delay'],0)
        self.assertEqual(stabilize(out,*args)[0],out)
        locked={'A':current['A']}
        out,_=stabilize(current,ns,current,locked,{'A':15},args[4],args[5],args[6])
        self.assertEqual(out['A'],locked['A'])
        self.assertEqual([out[k].rho for k in out],[current[k].rho for k in out])

    def test_actual_cifar_cost_and_window_formula(self):
        j=Job('unrelated-name',{'rtx':APPLICATIONS['rtx']['cifar10']},0,target_batch_size=128)
        self.assertEqual(application_costs([j])['cifar10']['rtx'],50)
        a=Allocation('rtx:0','rtx',1,3,62.5,1)
        b=replace(a,node='rtx:1',rho=1.75)
        args=({'A':a},{},{},{'A':'cifar10'},{'cifar10':{'rtx':50}},{'A'})
        self.assertAlmostEqual(evaluate({'A':b},*args,180)['phi']*180,227.5)
        self.assertAlmostEqual(evaluate({'A':b},*args,60)['phi']*60,17.5)

    def test_type_and_count_change_charge_once_and_lock_commit_retains_remaining(self):
        j=linear_job('A','rtx:0');j.applications['aws']=j.applications['rtx']
        j.perf_params['aws']=None;j.profiles['aws']={}
        old=Allocation('rtx:0','rtx',2,6,125,1);new=Allocation('aws:0','aws',4,12,250,1)
        nodes=[Node('rtx:0','rtx',4,12,250),Node('aws:0','aws',4,12,250)]
        p={'A':JobGpuPlan('A','aws',4,'aws:0',32,0)}
        e,_,pred=commit_v2([j],p,{'A':new},nodes,{'A':old},{},0,{}, {'A':'cifar10'},application_costs([j]),{'A'})
        self.assertEqual(e[0]['cost'],10);self.assertEqual(j.rescale_time,10)
        j.rescale_time=7
        e,_,pred=commit_v2([j],p,{'A':new},nodes,{'A':new},{'A':new},0,{'A':7},{'A':'cifar10'},application_costs([j]),{'A'})
        self.assertEqual(e,[]);self.assertEqual(pred['A']['new_cost'],0);self.assertEqual(j.rescale_time,7)
        j.step(3);self.assertEqual(j.rescale_time,4);self.assertEqual(j.progress,0)
