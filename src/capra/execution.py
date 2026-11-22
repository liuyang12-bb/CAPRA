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
