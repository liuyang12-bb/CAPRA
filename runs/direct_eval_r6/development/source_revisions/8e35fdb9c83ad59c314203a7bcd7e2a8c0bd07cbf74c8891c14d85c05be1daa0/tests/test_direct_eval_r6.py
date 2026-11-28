"""Only R6 integration risks; no new smoke/matrix, no new placement search."""
from pathlib import Path
from copy import deepcopy,copy
from types import SimpleNamespace
from unittest import mock
from dataclasses import asdict
import unittest,time,ast,os,json,sys,subprocess
from capra.protocol_direct_eval_r6 import ROOT,RUN,StopTracker,load
from capra.runtime_direct_eval_r6 import decide_f,decide_direct,advance_jobs
from capra.runner_direct_r5 import decide as old_decide
from capra.placement_direct_r5 import DirectPlacement
from capra.contracts import Node,JobGpuPlan,Allocation,serialized
from capra.response_v2 import V2Responses
from capra.audit_direct_eval_r6 import check_f_only

def fake_job(state):
    j=SimpleNamespace(name='c',progress=1.,execution_time=1.,rescale_time=30. if state=='locked' else 0.,num_restarts=None if state=='new' else 1,num_migrations=0,current_cluster=None if state=='new' else 'dgx-ext',placement=() if state=='new' else (1,),atomic_bsz=1,accum_steps=0,completion_time=None,submission_time=0.)
    def migrate(typ,shape):j.current_cluster=typ;j.placement=shape;j.rescale_time=50.;j.num_restarts=(j.num_restarts or 0)+1
    j.migrate=migrate;j.reallocate=lambda shape:migrate(j.current_cluster,shape)
    return j

class R6IntegrationTests(unittest.TestCase):
    def test_f_only_three_fixed_states_no_D_paths(self):
        nodes=[Node('dgx-ext:0','dgx-ext',8,24.,500.),Node('dgx-ext:1','dgx-ext',8,24.,500.)];costs={'cifar10':{'dgx-ext':50.}}
        receipts=[]
        for state in ('new','running','locked'):
            with self.subTest(state=state):
                response=V2Responses(ROOT/'data/scenarios_r1/responses_original.json');nid='dgx-ext:1';plan={'c':JobGpuPlan('c','dgx-ext',1,nid,1,0)}
                cpu=6. if state=='locked' else 3.;allocation=Allocation(nid,'dgx-ext',1,cpu,62.5,response.rho('cifar10',1,cpu,62.5));current={} if state=='new' else {'c':allocation};locks={'c':allocation} if state=='locked' else {};rem={'c':30.} if locks else {};seen=set(current)
                p=DirectPlacement(plan,nodes,{'c':'cifar10'},response,current,locks,rem,costs,seen);p.began=time.perf_counter();expected,_=p.prepare_f()
                stage=SimpleNamespace(choose=mock.Mock(return_value=(plan,dict(repairs=[],original_sia_plan={'c':dict(node=nid,gpu_type='dgx-ext',gpus=1)}))))
                with mock.patch.object(DirectPlacement,'select',side_effect=AssertionError('F_ONLY_SELECT_FORBIDDEN')),mock.patch.object(DirectPlacement,'construct_d',side_effect=AssertionError('F_ONLY_D_FORBIDDEN')),mock.patch('capra.placement_direct_r5.can_finish',side_effect=AssertionError('F_ONLY_DP_FORBIDDEN')):
                    a,r=decide_f(stage,[fake_job(state)],0.,current,locks,rem,{'c':'cifar10'},nodes,response,costs,seen)
                self.assertEqual(stage.choose.call_count,1);self.assertEqual(serialized(a),expected['allocations']);self.assertEqual(r['selection']['candidates'][0]['score'],expected['score']);self.assertEqual(r['commit_calls'],1)
                audited=check_f_only(dict(r,current=serialized(current),locks=serialized(locks),lock_remaining=rem,started=sorted(seen)),{n.id:asdict(n) for n in nodes},{'c':'cifar10'},response,{'cifar10':50.})
                self.assertEqual(audited,serialized(a));receipts.append(dict(state=state,status='PASS'))
        out=Path(os.environ['R6_VALIDATION_ARTIFACTS']);out.mkdir(parents=True,exist_ok=True);(out/'f_only_equivalence.json').write_text(json.dumps(receipts,indent=2),encoding='utf8')

    def test_direct_alias_and_real_Job_one_step_equivalence(self):
        self.assertIs(decide_direct,old_decide)
        from capra.upstream import Job,APPLICATIONS
        from capra.costs import application_costs
        row=next(iter(__import__('csv').DictReader((ROOT/'data/pressure_r4/saturn7_dense05.csv').open(encoding='utf8',newline=''))))
        job=Job(row['name'],{'dgx-ext':APPLICATIONS['dgx-ext'][row['application']]},float(row['time']),target_num_replicas=int(row['num_replicas']),target_batch_size=int(row['batch_size']))
        other=deepcopy(job);probe=copy(job);probe.current_cluster='dgx-ext';probe.placement=(1,);probe.update_local_bsz(probe.placement)
        p={job.name:JobGpuPlan(job.name,'dgx-ext',1,'dgx-ext:0',int(probe.atomic_bsz),int(probe.accum_steps))};nodes=[Node('dgx-ext:0','dgx-ext',8,24.,500.),Node('dgx-ext:1','dgx-ext',8,24.,500.)]
        meta=dict(repairs=[],original_sia_plan={job.name:dict(node='dgx-ext:0',gpu_type='dgx-ext',gpus=1)})
        stage=lambda:SimpleNamespace(choose=mock.Mock(return_value=(dict(p),deepcopy(meta))))
        response=lambda:V2Responses(ROOT/'data/scenarios_r1/responses_original.json')
        costs=application_costs([job]);args=({}, {},{}, {job.name:row['application']},nodes)
        a,old=old_decide(stage(),[job],float(row['time']),*args,response(),costs,set())
        b,new=decide_direct(stage(),[other],float(row['time']),*args,response(),costs,set())
        for key in ('plan','allocations','commit_predictions','transitions','node_usage'):self.assertEqual(old[key],new[key])
        self.assertEqual(old['selection']['selected'],new['selection']['selected']);self.assertEqual(old['selection']['contract'],new['selection']['contract'])
        # Compile only the frozen old execution loop for an exact one-step check.
        tree=ast.parse((ROOT/'src/capra/runner_direct_r5.py').read_text(encoding='utf8'))
        loop=next(n for n in ast.walk(tree) if isinstance(n,ast.For) and isinstance(n.target,ast.Name) and n.target.id=='j' and any(isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=='step' for x in ast.walk(n)))
        env=dict(jobs=[job],allocation=a,now=float(row['time']),interval=60,executions=[],asdict=asdict)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[loop],type_ignores=[])),'frozen_R5_one_step','exec'),env)
        actual=advance_jobs([other],b,float(row['time']),60);self.assertEqual(env['executions'],actual)

    def test_progress_and_overhead_stops(self):
        tracker=StopTracker()
        for i in range(40):self.assertIsNone(tracker.update(True,[dict(progress_before=i,progress_after=i+1)],.1))
        for i in range(29):self.assertIsNone(tracker.update(True,[dict(progress_before=0,progress_after=0)],.1))
        self.assertEqual(tracker.update(True,[dict(progress_before=0,progress_after=0)],.1),'NO_PROGRESS_30_ROUNDS')
        tracker=StopTracker()
        for i in range(40):self.assertIsNone(tracker.update(False,[],.1))
        self.assertIsNone(tracker.update(True,[],31));self.assertIsNone(tracker.update(True,[],31));self.assertEqual(tracker.update(True,[],31),'CONTROL_OVERHEAD_3X30S')

    def test_budget_cannot_reset_and_owned_grandchild_cleanup(self):
        sys.path.insert(0,str(ROOT/'scripts'));from budget_direct_eval_r6 import Budget,BP
        before=load(BP)
        with self.assertRaisesRegex(AssertionError,'EXPLICIT_RESUME'):Budget(resume=False)
        self.assertEqual(before,load(BP))
        from scenario_control import Owned,env
        out=Path(os.environ['R6_VALIDATION_ARTIFACTS']);out.mkdir(parents=True,exist_ok=True);log=out/'owned_tree.log'
        with log.open('w',encoding='utf8') as f:
            j=Owned([sys.executable,'-u','-c',"import subprocess,sys,time;subprocess.Popen([sys.executable,'-c','import time;time.sleep(20)']);print('READY',flush=True);time.sleep(20)"],f,env())
            try:
                end=time.monotonic()+3
                while 'READY' not in log.read_text(encoding='utf8') and time.monotonic()<end:time.sleep(.02)
                active=j.active();self.assertGreaterEqual(active,2)
            finally:receipt=j.close()
        self.assertEqual(receipt['active_after_cleanup'],0);(out/'owned_cleanup.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')

    def test_formal_metadata_and_portable_verification_contract(self):
        from capra.protocol_direct_eval_r6 import input_rows,cells,ORDER
        for w in ('saturn7_dense05','saturn8_dense05'):self.assertEqual(len(input_rows(ROOT/f'data/pressure_r4/{w}.csv')),80)
        self.assertEqual(len(cells()),8);self.assertEqual([(c['scenario'],c['method']) for c in cells()],ORDER)
        # Pure portable verifier must not mention or require any old worktree path.
        text=(ROOT/'scripts/verify_direct_eval_r6.py').read_text(encoding='utf8')
        self.assertNotIn('D:/科研启航',text);self.assertNotIn('D:\\科研启航',text)
        self.assertNotIn("HEAD')==R4",text)

if __name__=='__main__':unittest.main(verbosity=2)
