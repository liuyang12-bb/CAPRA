"""Small Direct-only adapter over frozen GpuStage/Job/commit and raw training audit."""
import argparse,csv,gzip,json,os,random,time,traceback,platform,hashlib
from pathlib import Path
from dataclasses import asdict
from datetime import datetime,timezone
import numpy as np
import scipy,cvxpy
from .upstream import ROOT,Job,APPLICATIONS,import_audit
from .contracts import Node,serialized
from .gpu_stage import GpuStage
from .response_v2 import V2Responses
from .execution import commit_v2
from .costs import application_costs
from .inputs import describe
from .placement_direct_r5 import DirectPlacement,BASE,VERSION,METHOD,gpu_contract,fingerprint
from .feasibility_direct_r5 import check_scope

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def convert(x):
    if isinstance(x,np.generic):return x.item()
    if isinstance(x,np.ndarray):return x.tolist()
    raise TypeError(type(x).__name__)
def dump(p,x):Path(p).write_bytes((json.dumps(x,ensure_ascii=False,indent=2,default=convert)+'\n').encode('utf8'))
def source_hashes():
    paths=list((ROOT/'src/capra').glob('*.py'))+list((ROOT/'third_party/sia/sia-simulator').glob('*.py'))+[ROOT/'requirements_v2.lock.txt']
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(paths)}
def live_snapshot(jobs):
    return [(j.name,j.progress,j.execution_time,j.rescale_time,j.num_restarts,j.num_migrations,j.current_cluster,tuple(j.placement),j.atomic_bsz,j.accum_steps,j.completion_time) for j in jobs]

def decide(stage,jobs,now,current,locks,remaining,apps,nodes,response,costs,started):
    begin=time.perf_counter();gpu_calls=0;commit_calls=0
    gpu_calls+=1;witness,gpu_meta=stage.choose(jobs,now,current,locks,response);gpu_seconds=time.perf_counter()-begin
    snapshot=live_snapshot(jobs);contract=gpu_contract(witness);digest=fingerprint(contract)
    placement=DirectPlacement(witness,nodes,apps,response,current,locks,remaining,costs,started)
    allocation,selection=placement.select()
    assert live_snapshot(jobs)==snapshot,'CANDIDATE_MUTATED_LIVE_JOB'
    assert contract==gpu_contract(witness) and digest==selection['contract_fingerprint'],'GPU_CONTRACT_BEFORE_COMMIT'
    selection['contract_checks'].append(dict(where='BEFORE_COMMIT',fingerprint=digest))
    begin_commit=time.perf_counter();commit_calls+=1
    transitions,usage,predictions=commit_v2(jobs,witness,allocation,nodes,current,locks,now,remaining,apps,costs,started)
    commit_seconds=time.perf_counter()-begin_commit
    chosen=next(c for c in selection['candidates'] if c['label']==selection['selected'])
    for k in witness:
        for field in ('new_cost','existing_remaining','delay'):assert abs(predictions[k][field]-chosen['score']['jobs'][k][field])<1e-8
    return allocation,dict(plan=serialized(witness),lock_repaired_gpu_plan=serialized(witness),raw_sia_plan=gpu_meta.get('original_sia_plan',{}),gpu_stage=gpu_meta,gpu_stage_calls=gpu_calls,commit_calls=commit_calls,selection=selection,transitions=transitions,node_usage=usage,commit_predictions=predictions,post_commit_remaining={j.name:float(j.rescale_time) for j in jobs if j.name in witness},gpu_stage_seconds=gpu_seconds,commit_seconds=commit_seconds,decision_seconds=time.perf_counter()-begin)

def run(input_path,cluster,responses,output,method=METHOD,allocator_mode='ram_slack_v1',max_jobs=8,max_rounds=60,interval=60,wall_limit=90):
    began=time.perf_counter();assert method==METHOD and allocator_mode=='ram_slack_v1' and interval==60
    output=Path(output).resolve();assert output.is_relative_to(ROOT/'runs/direct_r5') and not output.exists(),'NEW_R5_OUTPUT_REQUIRED';output.mkdir(parents=True)
    inputs={k:describe(p) for k,p in dict(workload=input_path,cluster=cluster,responses=responses).items()}
    random.seed(0);np.random.seed(0);nodes=[Node(**x) for x in json.loads(Path(cluster).read_text(encoding='utf8'))];check_scope(nodes,{})
    response=V2Responses(responses);rows=list(csv.DictReader(Path(input_path).open(encoding='utf8',newline='')))
    if max_jobs is not None:rows=rows[:max_jobs]
    assert rows,'NO_INPUT_JOBS'
    jobs=[Job(r['name'],{t:APPLICATIONS[t][r['application']] for t in dict.fromkeys(n.gpu_type for n in nodes)},float(r['time']),target_num_replicas=int(r['num_replicas']),target_batch_size=int(r['batch_size'])) for r in rows]
    stage=GpuStage(nodes,60,uniform_costs=True);costs=application_costs(jobs);imports=import_audit();imports['ROOT']=str(ROOT.resolve())
    hashes=source_hashes();provenance=fingerprint(dict(inputs=inputs,sources=hashes))
    start=dict(version=VERSION,base_commit=BASE,method=METHOD,allocator_mode=allocator_mode,candidate_labels=['F','D'],inputs=inputs,input=str(Path(input_path).resolve()),input_sha256=sha(input_path),cluster_sha256=sha(cluster),responses_sha256=sha(responses),max_jobs=max_jobs,max_rounds=max_rounds,interval=60,wall_limit=wall_limit,neutral=False,horizon=180,seed=0,placement_budget_seconds=5.,placement_budget_kind='COOPERATIVE_NOT_HARD',numeric_environment={k:os.environ.get(k) for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','PYTHONHASHSEED')},python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,cvxpy=cvxpy.__version__,dependency_lock_sha256=sha(ROOT/'requirements_v2.lock.txt'),costs=costs,import_audit=imports,source_files_sha256=hashes,provenance_fingerprint=provenance,utc=datetime.now(timezone.utc).isoformat(),formal_performance_experiment='NOT_RUN')
    dump(output/'start.json',start);current={};now=0.;status='ROUND_LIMIT';round_count=0
    try:
        with gzip.open(output/'events.jsonl.gz','wt',encoding='utf8') as log:
            for rid in range(max_rounds):
                if time.perf_counter()-began>wall_limit:status='WALL_LIMIT';break
                if (ROOT/'STOP_REQUEST.json').exists():status='USER_STOP';break
                active={j.name:j for j in jobs if j.completion_time is None};current={k:a for k,a in current.items() if k in active}
                locks={k:a for k,a in current.items() if active[k].rescale_time>1e-9};remaining={k:float(active[k].rescale_time) for k in locks}
                apps={j.name:j.app_name for j in jobs};started={j.name for j in jobs if j.num_restarts is not None}
                allocation,record=decide(stage,jobs,now,current,locks,remaining,apps,nodes,response,costs,started)
                executions=[]
                for j in jobs:
                    left=max(now,j.submission_time);right=now+interval
                    if left>=right or j.completion_time is not None:continue
                    j.current_time=left;j.capra_segments=[];progress=float(j.progress);training_before=j.execution_time;restore_before=j.rescale_time;a=allocation.get(j.name)
                    j.step(right-left);train=float(j.execution_time-training_before);restore=float(min(restore_before,right-left)) if a else 0.;end=float(j.completion_time) if j.completion_time is not None else right;wait=end-left-train-restore
                    assert wait>=-1e-7
                    executions.append(dict(job=j.name,start=left,end=end,allocation=asdict(a) if a else None,progress_before=progress,progress_after=float(j.progress),training=train,recovery=restore,waiting=max(0.,wait),completion_time=j.completion_time,segments=j.capra_segments,batch_after=dict(atomic_bsz=int(j.atomic_bsz),accum_steps=int(j.accum_steps)),rescale_remaining=float(j.rescale_time)))
                completed=sum(j.completion_time is not None for j in jobs)
                record.update(version=VERSION,method=METHOD,round=rid,time=now,interval=interval,current=serialized(current),locks=serialized(locks),lock_remaining=remaining,started=sorted(started),allocations=serialized(allocation),fallbacks=([dict(reason=record['selection']['D_status'])] if record['selection']['D_status']!='COMPLETE' else []),provenance_fingerprint=provenance,executions=executions,completed=completed,total=len(jobs))
                log.write(json.dumps(record,ensure_ascii=False,default=convert)+'\n');log.flush();round_count+=1;current=allocation;now=right
                if rid%10==0 or completed==len(jobs):print(json.dumps(dict(round=rid,completed=completed,total=len(jobs),selected=record['selection']['selected'],D_status=record['selection']['D_status'],decision_seconds=record['decision_seconds'],wall_seconds=time.perf_counter()-began)),flush=True)
                if completed==len(jobs):status='ALL_COMPLETE';break
        dump(output/'termination.json',dict(status=status,rounds=round_count,wall_seconds=time.perf_counter()-began,completed=sum(j.completion_time is not None for j in jobs),total=len(jobs),simulated_seconds=now))
    except Exception as error:
        dump(output/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),direct_diagnostic=getattr(error,'direct_diagnostic',None),wall_seconds=time.perf_counter()-began));raise
    dump(output/'output_hashes.json',{p.name:sha(p) for p in output.iterdir() if p.is_file() and p.name!='output_hashes.json'})
    from .audit_direct_r5 import audit
    result=audit(output);print(json.dumps(result,ensure_ascii=False),flush=True);return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',dest='input_path',required=True);p.add_argument('--cluster',required=True);p.add_argument('--responses',required=True);p.add_argument('--output',required=True)
    p.add_argument('--method',choices=[METHOD],default=METHOD);p.add_argument('--allocator-mode',choices=['ram_slack_v1'],default='ram_slack_v1');p.add_argument('--max-jobs',type=int,default=8);p.add_argument('--max-rounds',type=int,default=60);p.add_argument('--interval',type=int,default=60);p.add_argument('--wall-limit',type=float,default=90)
    run(**vars(p.parse_args()))
if __name__=='__main__':main()
