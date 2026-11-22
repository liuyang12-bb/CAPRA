import json,unittest
from dataclasses import replace,asdict
from pathlib import Path
import pandas as pd
from capra.contracts import Node,JobGpuPlan,Allocation,validate
from capra.tune import allocate
from capra.execution import commit
from capra.upstream import Job,import_audit,ROOT


class FixtureResponse:
    def rho(self,app,g,c,m):
        return min(c/(8 if app in 'AB' else 4),m/(50 if app in 'AB' else 200),1)
    def preferred(self,app,g,node):return (8,50) if app in 'AB' else (4,200)


class LinearApplication:
    """Explicit synthetic 600-unit fixture exercised through the real Sia Job.step."""
    name='cifar10';init_batch_size=128;min_local_bsz=1;max_local_bsz=64;max_batch_size=128
    max_epochs=1;num_stages=1;rescale_time=10
    placements=pd.DataFrame(dict(num_replicas=[2],local_bsz=[64]))
    def get_completion_epoch(self,batch):return 0
    def get_max_local_bsz(self,placement):return 64
    def get_grad_stats(self,batch,epoch):return (1,0)
    def get_throughput(self,placement,batch):return (.1,0)
    def get_progress(self,epoch):return 600*epoch
    def get_best_metric(self,batch,epoch):return 1


def linear_job(name,node):
    j=Job(name,{'rtx':LinearApplication()},0,target_batch_size=128,target_num_replicas=2)
    j.current_cluster='rtx';j.placement=(2,);j.atomic_bsz=64;j.accum_steps=0
    j.enable_bsz_tuning=False;j.calibration_factor=1;j.num_restarts=0
    # Test isolates execution, not profile learning; main runs use the unmodified update.
    j.update_params=lambda *args:None
    return j


class Contracts(unittest.TestCase):
    def setUp(self):
        self.nodes=[Node('rtx:0','rtx',4,12,250),Node('rtx:1','rtx',4,12,250)]
        self.plan={k:JobGpuPlan(k,'rtx',2,'rtx:0' if k in 'AB' else 'rtx:1',64,0) for k in 'ABCD'}
        self.apps={k:k for k in 'ABCD'};self.response=FixtureResponse()
        self.current={k:Allocation(p.node,'rtx',2,6,125,self.response.rho(k,2,6,125)) for k,p in self.plan.items()}

    def execute(self,alloc):
        jobs=[linear_job(k,self.plan[k].node) for k in 'ABCD']
        events,usage=commit(jobs,self.plan,alloc,self.nodes,self.current,{},0)
        for j in jobs:j.step(200)
        return jobs,events

    def test_complementarity_actual_execution_and_migration(self):
        fixed,fe=allocate(self.plan,self.nodes,self.apps,self.response,'fixed')
        free,ee=allocate(self.plan,self.nodes,self.apps,self.response,'free')
        self.assertEqual([free[k].node for k in 'ABCD'],['rtx:0','rtx:1','rtx:0','rtx:1'])
        self.assertEqual((free['A'].cpu,free['A'].ram),(8,50))
        self.assertEqual((free['C'].cpu,free['C'].ram),(4,200))
        a,ae=self.execute(fixed);b,be=self.execute(free)
        self.assertEqual([j.completion_time for j in a],[80,80,96,96])
        self.assertEqual([j.completion_time for j in b],[60,70,70,60])
        self.assertEqual(sum(e['kind']=='migration' for e in be),2)
        self.assertEqual(sum(j.execution_time for j in b),240)
        self.fixture=dict(fixed=asdict_results(fixed),free=asdict_results(free))

    def test_neutral_aux_change_no_gain_same_deployment(self):
        jobs=[linear_job('A','rtx:0'),linear_job('A','rtx:0')]
        jobs[0].capra_rho=jobs[1].capra_rho=1
        for j in jobs:j.rescale_time=10;j.step(15)
        self.assertEqual(jobs[0].progress,50)
        self.assertEqual(jobs[0].progress,jobs[1].progress)
        self.assertEqual(jobs[0].execution_time,5)

    def test_rho_once_recovery_and_wait_unscaled(self):
        j=linear_job('A','rtx:0');j.capra_rho=2;j.rescale_time=10;j.step(15)
        self.assertEqual(j.progress,100);self.assertEqual(j.execution_time,5);self.assertEqual(j.current_time,15)
        w=linear_job('A','rtx:0');w.reallocate(());w.capra_rho=2;w.step(15)
        self.assertEqual(w.progress,0);self.assertEqual(w.current_time,15)

    def test_exact_checkpoint_lock_and_complete_result(self):
        locks={'A':self.current['A']}
        a,events=allocate(self.plan,self.nodes,self.apps,self.response,'free',locks)
        self.assertEqual(a['A'],locks['A']);self.assertEqual(set(a),set(self.plan))
        validate(self.plan,a,self.nodes,locks)

    def test_partial_return_never_mutates_live_job(self):
        jobs=[linear_job(k,self.plan[k].node) for k in 'ABCD']
        before=[(j.progress,j.rescale_time,j.placement,j.current_cluster) for j in jobs]
        with self.assertRaisesRegex(AssertionError,'INCOMPLETE_JOB_SET'):
            commit(jobs,self.plan,{'A':self.current['A']},self.nodes,self.current,{},0)
        self.assertEqual(before,[(j.progress,j.rescale_time,j.placement,j.current_cluster) for j in jobs])

    def test_quota_only_update_does_not_migrate(self):
        jobs=[linear_job(k,self.plan[k].node) for k in 'ABCD']
        fixed,_=allocate(self.plan,self.nodes,self.apps,self.response,'fixed')
        events,_=commit(jobs,self.plan,fixed,self.nodes,self.current,{},0)
        self.assertFalse(any(e['kind']=='migration' for e in events))
        self.assertTrue(all(j.rescale_time==0 for j in jobs))

    def test_independent_environment_and_imports(self):
        self.assertEqual(Path(import_audit()['prefix']).resolve(),(ROOT/'.venv').resolve())

    def test_real_neutral_response_same_fixed_deployment(self):
        from capra.response import Responses
        response=Responses(ROOT/'data/responses.json',neutral=True)
        apps={k:'cifar10' for k in 'ABCD'}
        a,_=allocate(self.plan,self.nodes,apps,response,'fixed')
        self.assertTrue(all(x.rho==1 for x in a.values()))
        jobs,_=self.execute(a)
        self.assertEqual([j.completion_time for j in jobs],[60]*4)

    def test_actual_sia_stage_preserves_physical_restore_lock(self):
        from capra.gpu_stage import GpuStage
        from capra.response import Responses
        from capra.upstream import APPLICATIONS
        nodes=[Node('rtx:0','rtx',8,24,500),Node('rtx:1','rtx',8,24,500)]
        response=Responses(ROOT/'data/responses.json')
        j=Job('bert-0',{'rtx':APPLICATIONS['rtx']['bert']},0,target_num_replicas=1,target_batch_size=320)
        stage=GpuStage(nodes,60)
        plan,_=stage.choose([j],0,{}, {},response)
        a,_=allocate(plan,nodes,{'bert-0':'bert'},response,'fixed')
        commit([j],plan,a,nodes,{}, {},0)
        j.step(60)
        self.assertGreater(j.rescale_time,0)
        second,meta=stage.choose([j],60,a,a,response)
        self.assertEqual(second['bert-0'].node,a['bert-0'].node)
        held,_=allocate(second,nodes,{'bert-0':'bert'},response,'free',a)
        self.assertEqual(held,a)
        self.assertTrue(meta['physical_lock_constraints'])


def asdict_results(a):return {k:asdict(v) for k,v in a.items()}
if __name__=='__main__':unittest.main()
