import argparse
from dataclasses import asdict
from datetime import datetime,timezone
import csv,gzip,hashlib,json,os,random,sys,time,traceback
from pathlib import Path
import numpy as np
from .upstream import ROOT,Job,APPLICATIONS,import_audit
from .contracts import Node,serialized
from .response import Responses
from .gpu_stage import GpuStage
from .tune import allocate
from .execution import commit


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=convert)+'\n',encoding='utf8')
def convert(x):
    if isinstance(x,np.generic):return x.item()
    if isinstance(x,np.ndarray):return x.tolist()
    raise TypeError(str(type(x)))


def run(input_path,method,output,interval=60,max_rounds=6000,wall_limit=900,neutral=False,max_jobs=None):
    began=time.perf_counter()
    assert Path(input_path).resolve().is_relative_to(ROOT.resolve()),'FOREIGN_INPUT_PATH'
    output=Path(output).resolve()
    assert output.is_relative_to(ROOT.resolve()) and not output.exists()
    output.mkdir(parents=True)
    random.seed(0);np.random.seed(0)
    nodes=[Node(**n) for n in json.loads((ROOT/'configs/cluster.json').read_text())]
    response=Responses(ROOT/'data/responses.json',neutral=neutral)
    rows=list(csv.DictReader(Path(input_path).open(encoding='utf8',newline='')))
    if max_jobs is not None:rows=rows[:max_jobs]
    jobs=[Job(r['name'],{t:APPLICATIONS[t][r['application']] for t in dict.fromkeys(n.gpu_type for n in nodes)},float(r['time']),target_num_replicas=int(r['num_replicas']),target_batch_size=int(r['batch_size'])) for r in rows]
    stage=GpuStage(nodes,interval)
    dump(output/'start.json',dict(method=method,input=str(Path(input_path).resolve()),input_sha256=sha(input_path),cluster_sha256=sha(ROOT/'configs/cluster.json'),responses_sha256=sha(ROOT/'data/responses.json'),interval=interval,max_rounds=max_rounds,wall_limit=wall_limit,neutral=neutral,max_jobs=max_jobs,utc=datetime.now(timezone.utc).isoformat(),import_audit=import_audit()))
    current={};now=0.0;overheads=[];status='ROUND_LIMIT';stagnant=0;previous_progress=0
    try:
        with gzip.open(output/'events.jsonl.gz','wt',encoding='utf8') as log:
            for round_id in range(max_rounds):
                if time.perf_counter()-began>wall_limit:status='WALL_LIMIT';break
                if (ROOT/'STOP_REQUEST.json').exists():status='USER_STOP';break
                decision_start=time.perf_counter()
                current={k:a for k,a in current.items() if next(j for j in jobs if j.name==k).completion_time is None}
                locks={j.name:current[j.name] for j in jobs if j.name in current and j.rescale_time>1e-9 and j.completion_time is None}
                plan,gpu_meta=stage.choose(jobs,now,current,locks,response)
                gpu_seconds=time.perf_counter()-decision_start
                mode={'SIA-P':'proportional','CAPRA-Fixed':'fixed','CAPRA':'free'}[method]
                apps={j.name:j.app_name for j in jobs}
                allocations,fallbacks=allocate(plan,nodes,apps,response,mode,locks)
                transitions,usage=commit(jobs,plan,allocations,nodes,current,locks,now)
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
                record=dict(round=round_id,time=now,interval=interval,method=method,plan=serialized(plan),gpu_stage=gpu_meta,locks=serialized(locks),allocations=serialized(allocations),node_usage=usage,transitions=transitions,fallbacks=fallbacks,gpu_stage_seconds=gpu_seconds,decision_seconds=decision_seconds,executions=executions,completed=completed,total=len(jobs))
                log.write(json.dumps(record,ensure_ascii=False,default=convert)+'\n');log.flush()
                current=allocations;now=end
                progress=sum(j.progress for j in jobs)
                if now>=max(j.submission_time for j in jobs):
                    stagnant=stagnant+1 if progress<=previous_progress+1e-10 else 0
                previous_progress=progress
                if round_id%20==0 or completed==len(jobs):
                    print(json.dumps(dict(round=round_id,completed=completed,total=len(jobs),simulated_seconds=now,wall_seconds=round(time.perf_counter()-began,2),last_decision_seconds=round(decision_seconds,4))),flush=True)
                if completed==len(jobs):status='ALL_COMPLETE';break
                if stagnant>=30:status='NO_PROGRESS_30_ROUNDS';break
                if plan and len(overheads)>=3 and all(v>30 for v in overheads[-3:]):status='CONTROL_OVERHEAD_3X30S';break
        wall=time.perf_counter()-began
        dump(output/'termination.json',dict(status=status,rounds=round_id+1,wall_seconds=wall,completed=sum(j.completion_time is not None for j in jobs),total=len(jobs),simulated_seconds=now))
    except Exception as e:
        dump(output/'failure.json',dict(error=repr(e),traceback=traceback.format_exc(),wall_seconds=time.perf_counter()-began))
        raise
    dump(output/'output_hashes.json',{p.name:sha(p) for p in output.iterdir() if p.is_file() and p.name!='output_hashes.json'})
    from .audit import audit
    result=audit(output)
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--method',choices=['SIA-P','CAPRA-Fixed','CAPRA'],required=True);p.add_argument('--output',required=True)
    p.add_argument('--interval',type=int,default=60);p.add_argument('--max-rounds',type=int,default=6000);p.add_argument('--wall-limit',type=float,default=900);p.add_argument('--neutral',action='store_true');p.add_argument('--max-jobs',type=int)
    a=p.parse_args();run(a.input,a.method,a.output,a.interval,a.max_rounds,a.wall_limit,a.neutral,a.max_jobs)
if __name__=='__main__':main()
