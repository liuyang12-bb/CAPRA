"""Only the F-only adapter is new; Direct is the frozen R5 decide function itself."""
import time
from dataclasses import asdict
from .runner_direct_r5 import decide as decide_direct,live_snapshot
from .placement_direct_r5 import DirectPlacement,gpu_contract,fingerprint
from .contracts import serialized
from .execution import commit_v2

def decide_f(stage,jobs,now,current,locks,remaining,apps,nodes,response,costs,started):
    began=time.perf_counter();witness,gpu_meta=stage.choose(jobs,now,current,locks,response);gpu_seconds=time.perf_counter()-began
    snapshot=live_snapshot(jobs);contract=gpu_contract(witness);digest=fingerprint(contract)
    p=DirectPlacement(witness,nodes,apps,response,current,locks,remaining,costs,started)
    p.began=p.clock();hits,misses=response.hits,response.misses
    p.unchanged('BEFORE_F_ONLY');f,allocation=p.prepare_f();p.unchanged('AFTER_F_ONLY');p.check_alloc(allocation,True)
    s=p.trace;requests=s['solve_requests'];assert not s['steps'] and s['order'] is None and s['initial_check'] is None
    assert s['counts']['dp_checks']==s['counts']['preferred_queries']==s['counts']['budget_checks']==0
    assert all(r['phase']=='F' for r in requests)
    s['counts'].update(solve_requests=len(requests),cold_solves=len(s['allocation_traces']),cache_hits=sum(r['cache_hit'] for r in requests),response_hits=response.hits-hits,response_misses=response.misses-misses,response_queries=response.hits+response.misses-hits-misses,D_after_calls=0,D_construct_calls=0)
    s.update(D_status='NOT_APPLICABLE_F_ONLY',candidates=[f],candidate_labels=['F'],selected='F',phi=f['score']['phi'],relative_to_F=0.,reason='F_ONLY_NO_D_EXECUTION',horizon=180.,allocator=p.allocator.stats(),candidate_seconds=p.clock()-p.began,budget_seconds=5.,budget_overrun_seconds=0.)
    assert live_snapshot(jobs)==snapshot,'F_ONLY_MUTATED_LIVE_JOB'
    assert gpu_contract(witness)==contract and digest==s['contract_fingerprint']
    s['contract_checks'].append(dict(where='BEFORE_COMMIT',fingerprint=digest))
    commit_start=time.perf_counter();events,usage,predictions=commit_v2(jobs,witness,allocation,nodes,current,locks,now,remaining,apps,costs,started)
    commit_seconds=time.perf_counter()-commit_start
    for k in witness:
        for field in ('new_cost','existing_remaining','delay'):assert abs(predictions[k][field]-f['score']['jobs'][k][field])<1e-8
    return allocation,dict(plan=serialized(witness),lock_repaired_gpu_plan=serialized(witness),raw_sia_plan=gpu_meta.get('original_sia_plan',{}),gpu_stage=gpu_meta,gpu_stage_calls=1,commit_calls=1,selection=s,transitions=events,node_usage=usage,commit_predictions=predictions,post_commit_remaining={j.name:float(j.rescale_time) for j in jobs if j.name in witness},gpu_stage_seconds=gpu_seconds,commit_seconds=commit_seconds,decision_seconds=time.perf_counter()-began)

def advance_jobs(jobs,allocations,now,interval):
    """Same operations and fields as frozen R5's execution loop; original Job.step."""
    executions=[]
    for j in jobs:
        left=max(now,j.submission_time);right=now+interval
        if left>=right or j.completion_time is not None:continue
        j.current_time=left;j.capra_segments=[];progress=float(j.progress);training_before=j.execution_time;restore_before=j.rescale_time;a=allocations.get(j.name)
        j.step(right-left);train=float(j.execution_time-training_before);restore=float(min(restore_before,right-left)) if a else 0.;end=float(j.completion_time) if j.completion_time is not None else right;wait=end-left-train-restore
        assert wait>=-1e-7
        executions.append(dict(job=j.name,start=left,end=end,allocation=asdict(a) if a else None,progress_before=progress,progress_after=float(j.progress),training=train,recovery=restore,waiting=max(0.,wait),completion_time=j.completion_time,segments=j.capra_segments,batch_after=dict(atomic_bsz=int(j.atomic_bsz),accum_steps=int(j.accum_steps)),rescale_remaining=float(j.rescale_time)))
    return executions
