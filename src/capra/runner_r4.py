import argparse
from dataclasses import asdict
from datetime import datetime,timezone
import csv,gzip,hashlib,json,os,random,sys,time,traceback
from pathlib import Path
import numpy as np
from .upstream import ROOT,Job,APPLICATIONS,import_audit
from .contracts import Node,serialized
from .response_v2 import V2Responses as Responses
from .gpu_stage import GpuStage
from .execution import commit_v2
from .costs import application_costs
from .identity import reference
from .placement_r4 import create_placement
from .methods_r4 import spec,engine,VERSIONS
from .gpu_stage_r3 import SmartGpuStage
from .inputs import describe

VERSION='CAPRA_V2_PRESSURE_R4'
BASE='5af0bdb6b86b797225908f717b5b9324cd48a539'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=convert)+'\n',encoding='utf8')
def convert(x):
    if isinstance(x,np.generic):return x.item()
    if isinstance(x,np.ndarray):return x.tolist()
    raise TypeError(str(type(x)))


def run(input_path,method,output,interval=60,max_rounds=6000,wall_limit=900,neutral=False,max_jobs=None,cluster=None,responses=None,scenario_id=None,run_version=VERSION,allocator_mode="legacy",manifest=None):
    began=time.perf_counter()
    assert Path(input_path).resolve().is_relative_to(ROOT.resolve()),'FOREIGN_INPUT_PATH'
    output=Path(output).resolve()
    assert output.is_relative_to(ROOT.resolve()) and not output.exists()
    output.mkdir(parents=True)
    random.seed(0);np.random.seed(0)
    cluster=Path(cluster) if cluster is not None else ROOT/'configs/cluster.json'
    responses=Path(responses) if responses is not None else ROOT/'data/responses.json'
    inputs={k:describe(v) for k,v in dict(workload=input_path,cluster=cluster,responses=responses).items()}
    assert run_version in VERSIONS
    assert not neutral
    method_contract=spec(method,allocator_mode)
    import platform,scipy,cvxpy
    from .inputs import sha as input_sha
    frozen=json.loads(Path(manifest).read_text(encoding='utf8')) if manifest else None
    if frozen:
        assert frozen['version']==run_version and frozen['base_commit']==BASE
        for name,digest in frozen['files_sha256'].items():assert sha(ROOT/name)==digest,('FROZEN_CHANGED',name)
        assert sha(ROOT/frozen['source_snapshot'])==frozen['source_snapshot_sha256']
        match=[c for c in frozen['cells'] if c['scenario']==scenario_id and c['method']==method]
        assert len(match)==1 and match[0]['allocator_mode']==allocator_mode
        for kind,key in (('workload','input'),('cluster','cluster'),('responses','responses')):assert inputs[kind]['relative']==match[0][key]
    runtime_meta=dict(base_commit=BASE,phase_version=run_version,manifest_path=describe(manifest) if manifest else None,
        manifest_sha256=sha(manifest) if manifest else None,source_snapshot_sha256=frozen['source_snapshot_sha256'] if frozen else None,
        seed=0,process_limit_nominal=frozen['process_limit'] if frozen else 120,cost_model='Unchanged actual Application.rescale_time; aux-only zero',python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,cvxpy=cvxpy.__version__,
        solver='SCIPY/HiGHS;time_limit10;mip_rel_gap1e-4',dependency_lock_sha256=sha(ROOT/'requirements_v2.lock.txt'),
        numeric_environment={k:os.environ.get(k) for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','PYTHONHASHSEED')},
        placement_engine=engine(method),smart_provenance=json.loads((ROOT/'docs/CAPRA_R3_SMART_PROVENANCE.json').read_text(encoding='utf8')),total_budget_seconds=10800,**method_contract)
    nodes=[Node(**n) for n in json.loads(cluster.read_text())]
    response=Responses(responses,neutral=neutral)
    rows=list(csv.DictReader(Path(input_path).open(encoding='utf8',newline='')))
    if max_jobs is not None:rows=rows[:max_jobs]
    jobs=[Job(r['name'],{t:APPLICATIONS[t][r['application']] for t in dict.fromkeys(n.gpu_type for n in nodes)},float(r['time']),target_num_replicas=int(r['num_replicas']),target_batch_size=int(r['batch_size'])) for r in rows]
    stage=(SmartGpuStage if method=='SIA-SMART-P' else GpuStage)(nodes,interval,uniform_costs=True)
    costs=application_costs(jobs)
    dump(output/'start.json',dict(version=run_version,scenario_id=scenario_id,inputs=inputs,method=method,**runtime_meta,costs=costs,horizon=180,input=str(Path(input_path).resolve()),input_sha256=sha(input_path),cluster_sha256=sha(cluster),responses_sha256=sha(responses),interval=interval,max_rounds=max_rounds,wall_limit=wall_limit,neutral=neutral,max_jobs=max_jobs,utc=datetime.now(timezone.utc).isoformat(),import_audit=import_audit()))
    current={};now=0.0;overheads=[];status='ROUND_LIMIT';stagnant=0;previous_progress=0
    try:
        with gzip.open(output/'events.jsonl.gz','wt',encoding='utf8') as log:
            for round_id in range(max_rounds):
                if time.perf_counter()-began>wall_limit:status='WALL_LIMIT';break
                if (ROOT/'STOP_REQUEST.json').exists():status='USER_STOP';break
                decision_start=time.perf_counter()
                current={k:a for k,a in current.items() if next(j for j in jobs if j.name==k).completion_time is None}
                locks={j.name:current[j.name] for j in jobs if j.name in current and j.rescale_time>1e-9 and j.completion_time is None}
                remaining={j.name:float(j.rescale_time) for j in jobs if j.name in locks}
                apps={j.name:j.app_name for j in jobs}
                started={j.name for j in jobs if j.num_restarts is not None}
                plan,gpu_meta=stage.choose(jobs,now,current,locks,response)
                gpu_seconds=time.perf_counter()-decision_start
                gpu_meta.setdefault('placement_engine',engine(method))
                repaired_plan=serialized(plan)
                map_start=time.perf_counter()
                plan,ref_meta=reference(plan,nodes,current,locks,remaining,apps,costs,started,response)
                reference_seconds=time.perf_counter()-map_start
                placement=create_placement(plan,nodes,apps,response,current,locks,remaining,costs,started,method=method,allocator_mode=allocator_mode)
                allocations,selection=placement.select(method)
                commit_start=time.perf_counter()
                transitions,usage,committed=commit_v2(jobs,plan,allocations,nodes,current,locks,now,remaining,apps,costs,started)
                commit_seconds=time.perf_counter()-commit_start
                chosen=next(c for c in selection['candidates'] if c['label']==selection['selected'])
                for k in plan:
                    assert all(abs(committed[k][field]-chosen['score']['jobs'][k][field])<1e-8 for field in ('new_cost','existing_remaining','delay'))
                post_commit_remaining={j.name:float(j.rescale_time) for j in jobs if j.name in plan}
                decision_seconds=time.perf_counter()-decision_start
                if plan:overheads.append(decision_seconds)
                executions=[]
                for j in jobs:
                    start=max(now,j.submission_time)
                    end=now+interval
                    if start>=end or j.completion_time is not None:
                        continue
                    j.current_time=start
                    j.capra_segments=[]
                    before=float(j.progress); before_training=j.execution_time; before_restore=j.rescale_time
                    a=allocations.get(j.name)
                    j.step(end-start)
                    train=float(j.execution_time-before_training)
                    restore=float(min(before_restore,end-start)) if a else 0.0
                    active_end=float(j.completion_time) if j.completion_time is not None else end
                    wait=active_end-start-train-restore
                    assert wait>=-1e-7,(j.name,wait)
                    executions.append(dict(job=j.name,start=start,end=active_end,allocation=asdict(a) if a else None,
                        progress_before=before,progress_after=float(j.progress),training=train,recovery=restore,waiting=max(0.0,wait),completion_time=j.completion_time,
                        segments=j.capra_segments,batch_after=dict(atomic_bsz=int(j.atomic_bsz),accum_steps=int(j.accum_steps)),rescale_remaining=float(j.rescale_time)))
                completed=sum(j.completion_time is not None for j in jobs)
                record=dict(version=run_version,round=round_id,time=now,interval=interval,method=method,plan=serialized(plan),gpu_stage=gpu_meta,
                    raw_sia_plan=gpu_meta.get('original_sia_plan',{}),lock_repaired_gpu_plan=repaired_plan,reference=ref_meta,
                    current=serialized(current),locks=serialized(locks),lock_remaining=remaining,started=sorted(started),
                    allocations=serialized(allocations),node_usage=usage,transitions=transitions,fallbacks=[],selection=selection,
                    commit_predictions=committed,post_commit_remaining=post_commit_remaining,
                    gpu_stage_seconds=gpu_seconds,reference_seconds=reference_seconds,candidate_seconds=selection['candidate_seconds'],mapping_scoring_seconds=selection['mapping_scoring_seconds'],commit_seconds=commit_seconds,
                    response_cache=dict(size=len(response.cache),hits=response.hits,misses=response.misses),
                    decision_seconds=decision_seconds,executions=executions,completed=completed,total=len(jobs))
                log.write(json.dumps(record,ensure_ascii=False,default=convert)+'\n');log.flush()
                current=allocations;now=end
                progress=sum(j.progress for j in jobs)
                if now>=max(j.submission_time for j in jobs):
                    stagnant=stagnant+1 if progress<=previous_progress+1e-10 else 0
                previous_progress=progress
                if round_id%20==0 or completed==len(jobs):
                    print(json.dumps(dict(round=round_id,completed=completed,total=len(jobs),simulated_seconds=now,wall_seconds=round(time.perf_counter()-began,2),last_decision_seconds=round(decision_seconds,4),max_decision_seconds=round(max(overheads,default=0.),4))),flush=True)
                if completed==len(jobs):status='ALL_COMPLETE';break
                if stagnant>=30:status='NO_PROGRESS_30_ROUNDS';break
                if plan and len(overheads)>=3 and all(v>30 for v in overheads[-3:]):status='CONTROL_OVERHEAD_3X30S';break
        wall=time.perf_counter()-began
        dump(output/'termination.json',dict(status=status,rounds=round_id+1,wall_seconds=wall,completed=sum(j.completion_time is not None for j in jobs),total=len(jobs),simulated_seconds=now))
    except Exception as e:
        dump(output/'failure.json',dict(error=repr(e),traceback=traceback.format_exc(),wall_seconds=time.perf_counter()-began))
        raise
    dump(output/'output_hashes.json',{p.name:sha(p) for p in output.iterdir() if p.is_file() and p.name!='output_hashes.json'})
    from .audit_r4 import audit
    result=audit(output)
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--method',choices=['SIA-SMART-P','CAPRA-FK','CAPRA'],required=True);p.add_argument('--output',required=True)
    p.add_argument('--interval',type=int,default=60);p.add_argument('--max-rounds',type=int,default=6000);p.add_argument('--wall-limit',type=float,default=900);p.add_argument('--neutral',action='store_true');p.add_argument('--max-jobs',type=int)
    p.add_argument('--cluster');p.add_argument('--responses');p.add_argument('--scenario-id');p.add_argument('--run-version',default=VERSION)
    p.add_argument('--allocator-mode',choices=['none','legacy','ram_slack_v1'],required=True);p.add_argument('--manifest')
    a=p.parse_args();run(a.input,a.method,a.output,a.interval,a.max_rounds,a.wall_limit,a.neutral,a.max_jobs,a.cluster,a.responses,a.scenario_id,a.run_version,a.allocator_mode,a.manifest)
if __name__=='__main__':main()
