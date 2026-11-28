"""Formal 80-job closed loop, frozen R5 decisions; strict new metadata and stops."""
import argparse,csv,gzip,json,os,time,random,traceback,platform,sys
from pathlib import Path
import numpy as np
import scipy,cvxpy
from .protocol_direct_eval_r6 import ROOT,RUN,BASE,R4,VERSION,METHODS,NUMERIC,load,dump,sha,git,digest,input_rows,StopTracker
from .upstream import Job,APPLICATIONS,import_audit
from .contracts import Node,serialized
from .response_v2 import V2Responses
from .gpu_stage import GpuStage
from .costs import application_costs
from .feasibility_direct_r5 import check_scope
from .inputs import describe
from .runtime_direct_eval_r6 import decide_f,decide_direct,advance_jobs
from .runner_direct_r5 import convert

def run(manifest,cell,output,wall_limit=540.,global_deadline_epoch=None,global_deadline_monotonic=None):
    began=time.perf_counter();m=load(manifest);spec=next(c for c in m['cells'] if c['index']==cell)
    assert m['version']==VERSION and m['algorithm_base_commit']==BASE and spec['method'] in METHODS
    actual_head=git('rev-parse','HEAD').decode().strip()
    assert git('merge-base','--is-ancestor',m['actual_execution_head'],actual_head,check=False).returncode==0
    for p,h in m['execution_source_files_sha256'].items():assert sha(ROOT/p)==h,('FROZEN_EXECUTION_CHANGED',p)
    assert sha(ROOT/m['source_snapshot'])==m['source_snapshot_sha256']
    output=Path(output).resolve();assert output.is_relative_to(RUN) and not output.exists();output.mkdir(parents=True)
    assert {k:os.environ.get(k) for k in NUMERIC}==NUMERIC
    inputs={k:describe(ROOT/spec[key]) for k,key in (('workload','workload'),('cluster','cluster'),('responses','responses'))}
    rows=input_rows(ROOT/spec['workload']);random.seed(0);np.random.seed(0)
    nodes=[Node(**n) for n in load(ROOT/spec['cluster'])];check_scope(nodes,{})
    response=V2Responses(ROOT/spec['responses']);types=list(dict.fromkeys(n.gpu_type for n in nodes))
    jobs=[Job(r['name'],{t:APPLICATIONS[t][r['application']] for t in types},float(r['time']),target_num_replicas=int(r['num_replicas']),target_batch_size=int(r['batch_size'])) for r in rows]
    assert len(jobs)==80;stage=GpuStage(nodes,60,uniform_costs=True);costs=application_costs(jobs);imports=import_audit();imports['ROOT']=str(ROOT.resolve())
    method=spec['method'];manifest_rel=Path(manifest).resolve().relative_to(ROOT).as_posix()
    start=dict(version=VERSION,phase='FORMAL',formal_performance_experiment='RUNNING',method=method,candidate_labels=spec['candidate_labels'],allocator_mode='ram_slack_v1',algorithm_base_commit=BASE,inherited_direct_parent=R4,actual_execution_head=m['actual_execution_head'],legacy_R5_module_BASE_is_parent_only=R4,scenario=spec['scenario'],logical_cell=spec['logical_id'],inputs=inputs,input=inputs['workload']['absolute'],input_sha256=inputs['workload']['sha256'],cluster_sha256=inputs['cluster']['sha256'],responses_sha256=inputs['responses']['sha256'],max_jobs=None,jobs_loaded_count=80,expected_job_count=80,max_rounds=6000,interval=60,horizon=180,seed=0,placement_budget_seconds=5.,placement_budget_kind='COOPERATIVE_NOT_HARD',wall_limit=wall_limit,neutral=False,costs=costs,manifest_path=manifest_rel,manifest_sha256=sha(manifest),source_snapshot=m['source_snapshot'],source_snapshot_sha256=m['source_snapshot_sha256'],source_fingerprint=m['source_fingerprint'],numeric_environment=NUMERIC,python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,cvxpy=cvxpy.__version__,solver=m['environment']['solver'],highs_wrapper_sha256=m['environment']['highs_wrapper_sha256'],dependency_lock_sha256=sha(ROOT/'requirements_v2.lock.txt'),import_audit=imports,provenance_fingerprint=digest(dict(inputs=inputs,source=m['source_fingerprint'])),command=m['command_template'],global_deadline_epoch=global_deadline_epoch,global_deadline_monotonic=global_deadline_monotonic)
    start['actual_execution_head']=actual_head;start['frozen_code_head']=m['actual_execution_head'];start['command']=[sys.executable,*sys.argv]
    dump(output/'start.json',start);current={};now=0.;rounds=0;status='MAX_ROUNDS';tracker=StopTracker();implementation_error=None
    try:
        with gzip.open(output/'events.jsonl.gz','wt',encoding='utf8') as log:
            for rid in range(6000):
                if (global_deadline_epoch is not None and time.time()>=global_deadline_epoch) or (global_deadline_monotonic is not None and time.monotonic()>=global_deadline_monotonic):status='GLOBAL_BUDGET';break
                if time.perf_counter()-began>=wall_limit:status='WALL_LIMIT';break
                if (ROOT/'STOP_REQUEST.json').exists():status='USER_STOP';break
                active={j.name:j for j in jobs if j.completion_time is None};current={k:a for k,a in current.items() if k in active}
                locks={k:a for k,a in current.items() if active[k].rescale_time>1e-9};remaining={k:float(active[k].rescale_time) for k in locks}
                apps={j.name:j.app_name for j in jobs};started={j.name for j in jobs if j.num_restarts is not None}
                batch_before={j.name:dict(atomic_bsz=int(j.atomic_bsz),accum_steps=int(j.accum_steps)) for j in jobs if j.name in current}
                allocation,record=(decide_f if method=='CAPRA-F-Only' else decide_direct)(stage,jobs,now,current,locks,remaining,apps,nodes,response,costs,started)
                executions=advance_jobs(jobs,allocation,now,60);completed=sum(j.completion_time is not None for j in jobs)
                record.update(version=VERSION,phase='FORMAL',method=method,round=rid,time=now,interval=60,current=serialized(current),locks=serialized(locks),lock_remaining=remaining,started=sorted(started),allocations=serialized(allocation),batch_before=batch_before,fallbacks=([dict(reason=record['selection']['D_status'])] if method=='CAPRA-Direct' and record['selection']['D_status']!='COMPLETE' else []),provenance_fingerprint=start['provenance_fingerprint'],executions=executions,completed=completed,total=80)
                log.write(json.dumps(record,ensure_ascii=False,default=convert)+'\n');log.flush();rounds+=1;current=allocation;now+=60
                if rid%20==0 or completed==80:print(json.dumps(dict(round=rid,completed=completed,total=80,method=method,selected=record['selection']['selected'],D_status=record['selection']['D_status'],decision_seconds=record['decision_seconds'],wall_seconds=time.perf_counter()-began)),flush=True)
                if completed==80:status='ALL_COMPLETE';break
                stop=tracker.update(now>=max(j.submission_time for j in jobs),executions,record['decision_seconds'])
                if stop:status=stop;break
    except Exception as e:
        status='IMPLEMENTATION_ERROR';implementation_error=e;dump(output/'failure.json',dict(stage='DECISION_OR_EXECUTION',error=repr(e),traceback=traceback.format_exc(),direct_diagnostic=getattr(e,'direct_diagnostic',None)))
    term=dict(status=status,rounds=rounds,completed=sum(j.completion_time is not None for j in jobs),expected_job_count=80,submitted_count=sum(j.submission_time<=now for j in jobs),arrived_count=sum(j.submission_time<=now for j in jobs),simulated_seconds=now,wall_seconds=time.perf_counter()-began,execution_status='FAILED' if implementation_error else ('COMPLETE' if status=='ALL_COMPLETE' else 'PARTIAL'))
    dump(output/'termination.json',term)
    from .audit_direct_eval_r6 import derive_and_write
    try:
        summary=derive_and_write(output)
    except Exception as e:
        dump(output/'audit_failure.json',dict(stage='INDEPENDENT_AUDIT',error=repr(e),traceback=traceback.format_exc()));raise
    if implementation_error:raise implementation_error
    print(json.dumps(dict(status=summary['execution_status'],audit=summary['audit_status'],completed=summary['completed_count'],mean_jct=summary['mean_jct'],decision=summary['decision_distribution'])),flush=True)
    return summary

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--cell',type=int,required=True);p.add_argument('--output',required=True);p.add_argument('--wall-limit',type=float,default=540.);p.add_argument('--global-deadline-epoch',type=float);p.add_argument('--global-deadline-monotonic',type=float)
    run(**vars(p.parse_args()))
if __name__=='__main__':main()
