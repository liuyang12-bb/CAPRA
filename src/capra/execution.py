"""Physical-identity-aware commit; a pure candidate never touches live Job state."""
from dataclasses import asdict
from .contracts import validate


def commit(jobs, plan, allocations, nodes, current, locks, now):
    usage=validate(plan,allocations,nodes,locks)
    events=[]
    for job in jobs:
        if job.submission_time>now or job.completion_time is not None:
            continue
        new=allocations.get(job.name)
        old=current.get(job.name)
        if new is None:
            if old is not None:
                assert job.name not in locks
                job.reallocate(())
                events.append(dict(job=job.name,kind='suspend',old=asdict(old),new=None,cost=0.0))
            continue
        gpu_changed=old is None or (old.node,old.gpu_type,old.gpus)!=(new.node,new.gpu_type,new.gpus)
        if gpu_changed:
            assert job.name not in locks
            previously_started=job.num_restarts is not None
            if job.current_cluster!=new.gpu_type:
                job.migrate(new.gpu_type,(new.gpus,))
            elif tuple(job.placement)!=(new.gpus,):
                job.reallocate((new.gpus,))
            else:
                # Upstream reallocate ignores equal shape; explicitly charge node identity changes.
                job.rescale_time=job.applications[new.gpu_type].rescale_time or 30
                job.num_restarts=(job.num_restarts or 0)+1
            kind=('resume' if previously_started else 'start') if old is None else ('migration' if old.node!=new.node else 'reconfigure')
            events.append(dict(job=job.name,kind=kind,old=asdict(old) if old else None,new=asdict(new),cost=float(job.rescale_time)))
        elif old!=new:
            events.append(dict(job=job.name,kind='aux_update',old=asdict(old),new=asdict(new),cost=0.0))
        job.capra_rho=new.rho
        p=plan[job.name]
        assert job.atomic_bsz==p.atomic_bsz and job.accum_steps==p.accum_steps,'BATCH_SNAPSHOT_MISMATCH'
    return events,usage


def commit_v2(jobs,plan,allocations,nodes,current,locks,now,remaining,apps,costs,started):
    from .costs import transition
    usage=validate(plan,allocations,nodes,locks)
    predictions={j.name:transition(j.name,allocations.get(j.name),current,locks,remaining,apps,costs,started)
        for j in jobs if j.submission_time<=now and j.completion_time is None}
    events=[]
    for job in jobs:
        if job.name not in predictions:continue
        t=predictions[job.name];a=allocations.get(job.name);old=current.get(job.name)
        if a is None:
            if t['kind']=='suspend':job.reallocate(())
        elif t['gpu_change']:
            if job.current_cluster!=a.gpu_type:job.migrate(a.gpu_type,(a.gpus,))
            elif tuple(job.placement)!=(a.gpus,):job.reallocate((a.gpus,))
            else:
                job.rescale_time=t['new_cost'];job.num_restarts=(job.num_restarts or 0)+1
            assert abs(job.rescale_time-t['new_cost'])<1e-9,'PREDICTION_COMMIT_COST_MISMATCH'
        elif t['kind']=='locked':
            assert abs(job.rescale_time-t['existing_remaining'])<1e-9
        if a is not None:
            job.capra_rho=a.rho
            p=plan[job.name]
            assert (job.atomic_bsz,job.accum_steps)==(p.atomic_bsz,p.accum_steps),'BATCH_SNAPSHOT_MISMATCH'
        if t['kind'] not in ('unchanged','locked'):
            events.append(dict(job=job.name,kind=t['kind'],old=asdict(old) if old else None,new=asdict(a) if a else None,
                cost=t['new_cost'],prediction=t,remaining_after=float(job.rescale_time)))
    return events,usage,predictions
