"""Isolated correctness fixtures only; never performance experiments or new profiles."""
import unittest,itertools,copy,json,os
from pathlib import Path
from unittest import mock
from dataclasses import replace
from types import SimpleNamespace
from capra.contracts import Node,JobGpuPlan,Allocation,serialized
from capra.response_v2 import V2Responses
from capra.placement_direct_r5 import DirectPlacement,better_node,better_complete,gpu_contract
from capra.feasibility_direct_r5 import can_finish,check_scope
from capra.audit_direct_r5 import audit_selection,possible
from capra.costs import evaluate,transition

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('R5_TEST_ARTIFACTS',ROOT/'runs/direct_r5/test_artifacts'))
OUT.mkdir(parents=True,exist_ok=True)
def save(name,x):(OUT/name).write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def nodes():return [Node('dgx-ext:0','dgx-ext',8,24.,500.),Node('dgx-ext:1','dgx-ext',8,24.,500.)]
def response():return V2Responses(ROOT/'data/scenarios_r1/responses_original.json')
def fees(c=50.,b=120.):return {'cifar10':{'dgx-ext':c},'bert':{'dgx-ext':b}}
def plan(names,g=4):return {k:JobGpuPlan(k,'dgx-ext',g,'dgx-ext:'+('0' if k.startswith('c') else '1'),1,0) for k in names}
def mechanism(cost_zero=True):
    ns=nodes();r=response();p=plan(('c0','c1','b0','b1'));apps={k:'cifar10' if k.startswith('c') else 'bert' for k in p}
    cur={k:Allocation(q.node,q.gpu_type,q.gpus,12.,250.,r.rho(apps[k],4,12.,250.)) for k,q in p.items()}
    return p,ns,apps,r,cur,{}, {},fees(0,0) if cost_zero else fees(),set(p)
def checked(args,**kwargs):
    p=DirectPlacement(*args,**kwargs);a,s=p.select();w,ns,apps,r,cur,locks,rem,costs,seen=args
    assert audit_selection(serialized(w),s,{n.id:vars(n) for n in ns},apps,r,serialized(cur),serialized(locks),rem,costs,seen)==serialized(a)
    return p,a,s

class DirectTests(unittest.TestCase):
    def test_E_real_frozen_complement_and_physical_nodes(self):
        args=mechanism();before=copy.deepcopy(args[0:3]+args[4:]);p,a,s=checked(args)
        f,d=s['candidates'];self.assertEqual(s['selected'],'D');self.assertAlmostEqual(f['score']['phi'],4.)
        self.assertAlmostEqual(d['score']['phi'],5.06)
        for nid in ('dgx-ext:0','dgx-ext:1'):
            ids=[k for k,x in a.items() if x.node==nid];self.assertEqual(len(ids),2)
            self.assertEqual({args[2][k] for k in ids},{'cifar10','bert'})
            c=next(a[k] for k in ids if k.startswith('c'));b=next(a[k] for k in ids if k.startswith('b'))
            self.assertAlmostEqual(c.cpu,20.);self.assertAlmostEqual(c.ram,250.);self.assertAlmostEqual(c.rho,1.53)
            self.assertAlmostEqual(b.cpu,4.);self.assertAlmostEqual(b.ram,83.32);self.assertAlmostEqual(b.rho,1.)
        self.assertTrue(any(a[k].node!=args[4][k].node for k in a))
        self.assertEqual(before,args[0:3]+args[4:])
        save('mechanism_fixture.json',dict(label='ISOLATED_TEST_ZERO_STARTUP_FEES_NOT_PERFORMANCE',sum_rho_F=f['score']['phi'],sum_rho_D=d['score']['phi'],witness=serialized(args[0]),current=serialized(args[4]),selection=s))

    def test_D_entire_node_peer_loss_and_raw_rho_cost_tradeoff(self):
        args=mechanism();_,_,s=checked(args);peer_loss=[]
        for step in s['steps']:
            for c in step['candidates']:
                if 'after_trace_id' not in c:continue
                before=s['allocation_traces'][c['before_trace_id']];after=s['allocation_traces'][c['after_trace_id']]
                peer_loss += [(step['job'],c['delta']) for k,a in before['allocations'].items() if after['allocations'][k]['rho']<a['rho']-1e-9]
        self.assertTrue(peer_loss)
        ns=nodes();r=response();p=plan(('bL',));p['bL']=replace(p['bL'],node=ns[1].id)
        p['c']=JobGpuPlan('c','dgx-ext',1,ns[1].id,1,0)
        apps={'bL':'bert','c':'cifar10'};lock=Allocation(ns[1].id,'dgx-ext',4,20.,250.,r.rho('bert',4,20,250))
        cur={'bL':lock,'c':Allocation(ns[1].id,'dgx-ext',1,3.,62.5,r.rho('cifar10',1,3,62.5))}
        _,a,s=checked((p,ns,apps,r,cur,{'bL':lock},{'bL':30.},fees(120,120),set(cur)))
        choices=s['steps'][0]['candidates'];left,right=choices
        trace=s['allocation_traces'];lr=trace[left['after_trace_id']]['allocations']['c']['rho'];rr=trace[right['after_trace_id']]['allocations']['c']['rho']
        self.assertGreater(lr,rr);self.assertLess(left['delta'],right['delta']);self.assertEqual(s['steps'][0]['chosen_node'],ns[1].id)

    def test_D_all_negative_candidates_still_finish(self):
        p,ns,apps,r,cur,locks,rem,costs,seen=mechanism(False)
        cur={k:a for k,a in cur.items() if k.startswith('c')};seen=set(cur);costs=fees(50,200)
        _,a,s=checked((p,ns,apps,r,cur,locks,rem,costs,seen))
        self.assertEqual(set(a),set(p));negative=[]
        for step in s['steps']:
            opts=[c for c in step['candidates'] if 'delta' in c]
            if opts and all(c['delta']<=0 for c in opts):negative.append(step['job'])
        self.assertTrue(negative);self.assertEqual(s['D_status'],'COMPLETE')
        args=mechanism();args=list(args);args[7]=fees(200,200);args[4]={};args[8]=set()
        _,_,s=checked(tuple(args));self.assertTrue(all(c['delta']==0 for st in s['steps'] for c in st['candidates'] if 'delta' in c))

    def test_A_empty_all_locked_single_node_and_type_isolation(self):
        ns=nodes();r=response();_,a,s=checked(({},ns,{},r,{}, {},{},fees(),set()))
        self.assertEqual(a,{});self.assertEqual(s['selected'],'F')
        p=plan(('c',),1);cur={'c':Allocation(ns[0].id,'dgx-ext',1,6.,62.5,r.rho('cifar10',1,6,62.5))};p['c']=replace(p['c'],node=ns[0].id)
        _,a,s=checked((p,ns,{'c':'cifar10'},r,cur,cur,{'c':30.},fees(),{'c'}));self.assertEqual(a,cur);self.assertEqual(s['order'],[])
        p={'c':p['c']};_,a,_=checked((p,[ns[0]],{'c':'cifar10'},response(),{}, {},{},fees(),set()));self.assertEqual(a['c'].node,ns[0].id)
        other=Node('rtx:0','rtx',8,24.,500.);p['x']=JobGpuPlan('x','rtx',1,'rtx:0',1,0);cost=fees();cost['bert']['rtx']=120.
        _,a,_=checked((p,[ns[0],other],{'c':'cifar10','x':'bert'},response(),{}, {},{},cost,set()));self.assertEqual(a['x'].gpu_type,'rtx')
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_SCOPE'):check_scope(ns+[Node('dgx-ext:2','dgx-ext',8,24,500)],{})
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_SCOPE'):check_scope(ns,{'c':dict(gpu_contract({'c':replace(p['c'],nodes=2)})['c'])})

    def test_B_fixed_order_dictionary_and_F_witness_independence(self):
        args=mechanism();_,_,base=checked(args)
        reversed_args=list(args);reversed_args[0]=dict(reversed(list(args[0].items())));reversed_args[1]=list(reversed(args[1]));reversed_args[4]=dict(reversed(list(args[4].items())))
        _,_,other=checked(tuple(reversed_args))
        def semantic(s):
            d=s['candidates'][1];return s['order'],d['allocations'],[(x['job'],x['chosen_node'],[(c['node'],c.get('delta'),c['can_finish']['feasible']) for c in x['candidates']]) for x in s['steps']]
        self.assertEqual(semantic(base),semantic(other))
        changed=list(args);changed[0]={k:replace(p,node='dgx-ext:'+('1' if p.node.endswith('0') else '0')) for k,p in args[0].items()}
        _,_,other=checked(tuple(changed));self.assertEqual(semantic(base),semantic(other))
        self.assertEqual(base['order'],['c0','c1','b0','b1'])

    def test_B_node_and_complete_ties(self):
        a=dict(delta=1.,inserted_new_cost=50.,keeps_current_node=False,node='b');b=dict(a,node='a')
        self.assertFalse(better_node(a,b));self.assertTrue(better_node(dict(a,keeps_current_node=True),b))
        self.assertTrue(better_node(dict(a,inserted_new_cost=25.),dict(b,keeps_current_node=True)))
        self.assertTrue(better_node(dict(a,delta=1.+2e-9),dict(b,inserted_new_cost=0.)))
        f=dict(phi=2.,total_delay=50.,changes=2)
        self.assertFalse(better_complete(f,dict(f)));self.assertTrue(better_complete(dict(f,changes=1),f))
        self.assertTrue(better_complete(dict(f,total_delay=25.,changes=9),f));self.assertTrue(better_complete(dict(f,phi=3.,total_delay=200.),f))

    def test_C_asymmetric_real_lock_effective_capacity(self):
        ns=nodes();r=response();p=plan(('bL',));p['bL']=replace(p['bL'],node=ns[0].id)
        for k,g in [('c0',4),('c1',4),('c2',1)]:p[k]=JobGpuPlan(k,'dgx-ext',g,ns[1].id if g==4 else ns[0].id,1,0)
        apps={k:'bert' if k=='bL' else 'cifar10' for k in p};lock=Allocation(ns[0].id,'dgx-ext',4,20.,250.,r.rho('bert',4,20,250));locks={'bL':lock};c=gpu_contract(p)
        root={'bL':ns[0].id};v=can_finish(c,ns,apps,r,locks,root,['c0','c1','c2']);self.assertTrue(v['feasible']);self.assertEqual(v['reservations'][ns[0].id]['effective_gpus'],1)
        self.assertFalse(can_finish(c,ns,apps,r,locks,dict(root,c2=ns[1].id),['c0','c1'])['feasible'])
        self.assertTrue(can_finish(c,ns,apps,r,locks,dict(root,c2=ns[0].id),['c0','c1'])['feasible'])
        _,a,s=checked((p,ns,apps,r,locks,locks,{'bL':30.},fees(),{'bL'}))
        self.assertEqual(s['candidates'][1]['allocations']['c2']['node'],ns[0].id)
        self.assertEqual(a['bL'],lock)

    def test_C_small_independent_exhaustive_completion(self):
        tested=0;ns=[Node('dgx-ext:0','dgx-ext',4,12.,250.),Node('dgx-ext:1','dgx-ext',4,12.,250.)];r=response();nm={n.id:vars(n) for n in ns}
        for gs in itertools.product((1,2),repeat=3):
            p={str(i):JobGpuPlan(str(i),'dgx-ext',g,ns[0].id,1,0) for i,g in enumerate(gs)};c=gpu_contract(p);apps={k:'bert' for k in p}
            for first in (None,ns[0].id,ns[1].id):
                partial={} if first is None else {'0':first};todo=sorted(set(p)-set(partial));brute=False
                for assignment in itertools.product([n.id for n in ns],repeat=len(todo)):
                    layout=dict(partial);layout.update(zip(todo,assignment));valid=True
                    for n in ns:
                        ids=[k for k,v in layout.items() if v==n.id];g=sum(gs[int(k)] for k in ids)
                        valid &= g<=n.gpus and g*n.cpu/n.gpus<=n.cpu+1e-7 and g*n.ram/n.gpus<=n.ram+1e-7
                    brute |= valid
                self.assertEqual(can_finish(c,ns,apps,r,{},partial,todo)['feasible'],brute)
                self.assertEqual(possible(c,nm,{},r,partial,todo)[0],brute);tested+=1
        save('completion_bruteforce.json',dict(status='PASS',isolated_states=tested,max_jobs=3,max_assignments_per_state=8,no_online_search_change=True))

    def test_F_complete_F_win_D_win_tie_and_cooperative_budget(self):
        args=mechanism(False);_,_,s=checked(args);self.assertEqual(s['selected'],'F');self.assertLess(s['candidates'][1]['score']['phi'],s['candidates'][0]['score']['phi'])
        _,_,s=checked(mechanism());self.assertEqual(s['selected'],'D')
        _,_,s=checked(mechanism(),budget_seconds=0);self.assertEqual(s['D_status'],'D_NOT_STARTED_BUDGET');self.assertNotIn('score',s['candidates'][1])
        class Clock:
            value=0.
            def __call__(self):return self.value
        for closed_prefix in (False,True):
            args=mechanism();clock=Clock();p=DirectPlacement(*args,clock=clock)
            if closed_prefix:
                original=p.budget_check
                def guard():
                    if p.trace['steps'] and p.trace['steps'][0]['complete']:clock.value=10.
                    original()
                p.budget_check=guard
            else:
                original=p.solve
                def solve(nid,ids,phase):
                    value=original(nid,ids,phase)
                    if phase=='D_AFTER':clock.value=10.
                    return value
                p.solve=solve
            a,s=p.select();audit_selection(serialized(args[0]),s,{n.id:vars(n) for n in args[1]},args[2],args[3],serialized(args[4]),{}, {},args[7],args[8])
            self.assertEqual(s['D_status'],'D_BUDGET');self.assertEqual(s['selected'],'F');self.assertNotIn('allocations',s['candidates'][1])
            self.assertEqual(len(s['prefix_layout']),1 if closed_prefix else 0)
            save('budget_prefix_'+str(closed_prefix)+'.json',dict(label='TEST_FAKE_CLOCK_NOT_TIMING_EVIDENCE',selection=s))

    def test_F_exactly_three_R4_F_replays_and_old_paths(self):
        from capra.identity import reference
        from capra.placement_r4 import create_placement
        fixtures=[mechanism(),mechanism(False)]
        ns=nodes();r=response();p=plan(('c',),1);cur={'c':Allocation(ns[0].id,'dgx-ext',1,3.,62.5,1.)};fixtures.append((p,ns,{'c':'cifar10'},r,cur,cur,{'c':10.},fees(),{'c'}))
        results=[]
        for index,args in enumerate(fixtures):
            p,ns,apps,r,cur,locks,rem,costs,seen=args
            _,_,s=checked(args);ref,_=reference(p,ns,cur,locks,rem,apps,costs,seen,r)
            old=create_placement(ref,ns,apps,r,cur,locks,rem,costs,seen,method='CAPRA-FK',allocator_mode='ram_slack_v1').fixed()
            self.assertEqual(serialized(old['allocations']),s['candidates'][0]['allocations']);self.assertEqual(old['score'],s['candidates'][0]['score']);results.append(dict(index=index,status='PASS'))
        save('F_replay_results.json',dict(status='PASS',states=results,total_states=3,no_historical_simulation=True))
        from capra.placement import Placement
        import capra.identity as identity
        with mock.patch.object(Placement,'reordered',side_effect=AssertionError('R_FORBIDDEN')),mock.patch.object(Placement,'retained',side_effect=AssertionError('K_FORBIDDEN')),mock.patch.object(Placement,'finish',side_effect=AssertionError('FINISH_FORBIDDEN')),mock.patch.object(identity,'stabilize',wraps=identity.stabilize) as st:
            checked(mechanism());self.assertEqual(st.call_count,1)

    def test_G_independent_audit_rejects_delta_delay_and_physical_node(self):
        args=mechanism();_,_,s=checked(args);rejections=[]
        for field in ('delta','delay','node'):
            bad=copy.deepcopy(s)
            if field=='delta':next(c for st in bad['steps'] for c in st['candidates'] if 'delta' in c)['delta']+=1
            elif field=='delay':next(t for t in bad['allocation_traces'] if t['score']['jobs'])['score']['jobs'][next(k for t in bad['allocation_traces'] for k in t['score']['jobs'])]['delay']+=1
            else:
                d=bad['candidates'][1];k=next(iter(d['allocations']));d['allocations'][k]['node']='dgx-ext:9'
            with self.assertRaises((AssertionError,KeyError)):
                audit_selection(serialized(args[0]),bad,{n.id:vars(n) for n in args[1]},args[2],args[3],serialized(args[4]),{}, {},args[7],args[8])
            save('tampered_'+field+'.json',dict(label='INTENTIONAL_TEST_TAMPERING',selection=bad));rejections.append(dict(field=field,rejected=True))
        save('tamper_rejections.json',dict(status='PASS',rejections=rejections))

    def test_A_GPU_and_commit_once_no_candidate_Job_step(self):
        from capra.runner_direct_r5 import decide
        from capra.execution import commit_v2
        ns=nodes();r=response();p=plan(('c',),1);p['c']=replace(p['c'],node=ns[0].id)
        cur={'c':Allocation(ns[0].id,'dgx-ext',1,3.,62.5,1.)}
        j=SimpleNamespace(name='c',progress=1.,execution_time=1.,rescale_time=0.,num_restarts=1,num_migrations=0,current_cluster='dgx-ext',placement=(1,),atomic_bsz=1,accum_steps=0,completion_time=None,submission_time=0.)
        j.step=mock.Mock(side_effect=AssertionError('CANDIDATE_STEP_FORBIDDEN'))
        stage=SimpleNamespace(choose=mock.Mock(return_value=(p,dict(repairs=[],original_sia_plan={k:dict(node=v.node,gpu_type=v.gpu_type,gpus=v.gpus) for k,v in p.items()}))))
        with mock.patch('capra.runner_direct_r5.commit_v2',wraps=commit_v2) as commit:
            a,record=decide(stage,[j],0.,cur,{}, {},{'c':'cifar10'},ns,r,fees(),{'c'})
            self.assertEqual(stage.choose.call_count,1);self.assertEqual(commit.call_count,1);j.step.assert_not_called()
        self.assertEqual(record['gpu_stage_calls'],1);self.assertEqual(record['commit_calls'],1)
        # Configuration and node change is charged exactly once by the existing commit.
        p={'c':JobGpuPlan('c','dgx-ext',2,ns[1].id,1,0)};new={'c':Allocation(ns[1].id,'dgx-ext',2,6.,125.,1.)}
        def reallocate(shape):j.placement=shape;j.rescale_time=50.;j.num_restarts+=1
        j.reallocate=mock.Mock(side_effect=reallocate)
        _,_,pred=commit_v2([j],p,new,ns,cur,{},0.,{}, {'c':'cifar10'},fees(),{'c'})
        self.assertEqual(pred['c']['new_cost'],50.);self.assertEqual(j.rescale_time,50.);self.assertEqual(j.reallocate.call_count,1)

    def test_A_invalid_complete_witness_is_failure_not_passed_fallback(self):
        args=list(mechanism());args[0]={k:replace(p,node='dgx-ext:0') for k,p in args[0].items()}
        with self.assertRaises(AssertionError):DirectPlacement(*args).select()

if __name__=='__main__':unittest.main(verbosity=2)
