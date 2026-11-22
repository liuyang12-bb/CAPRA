from dataclasses import dataclass, asdict
from typing import Mapping


@dataclass(frozen=True)
class Node:
    id: str
    gpu_type: str
    gpus: int
    cpu: float
    ram: float


@dataclass(frozen=True)
class JobGpuPlan:
    name: str
    gpu_type: str
    gpus: int
    node: str
    atomic_bsz: int
    accum_steps: int
    nodes: int = 1

    @property
    def shape(self):
        return (self.gpus,)


@dataclass(frozen=True)
class Allocation:
    node: str
    gpu_type: str
    gpus: int
    cpu: float
    ram: float
    rho: float


def validate(plan: Mapping[str, JobGpuPlan], allocations: Mapping[str, Allocation], nodes, locks=None):
    """Pure check: a partial result can never be committed."""
    assert set(plan) == set(allocations), 'INCOMPLETE_JOB_SET'
    node_map = {n.id:n for n in nodes}
    used = {n.id:[0,0.0,0.0] for n in nodes}
    for name, a in allocations.items():
        p = plan[name]
        assert p.nodes == 1 and p.gpus == a.gpus and p.gpu_type == a.gpu_type
        n = node_map[a.node]
        assert n.gpu_type == a.gpu_type
        assert a.gpus > 0 and a.cpu > 0 and a.ram > 0 and a.rho > 0
        for i,v in enumerate((a.gpus,a.cpu,a.ram)):
            used[n.id][i] += v
        if locks and name in locks:
            assert a == locks[name], 'CHECKPOINT_LOCK_CHANGED'
    for n in nodes:
        assert all(x <= cap+1e-7 for x,cap in zip(used[n.id],(n.gpus,n.cpu,n.ram))), ('NODE_CAPACITY',n.id,used[n.id])
    return used


def serialized(mapping):
    return {k:asdict(v) for k,v in mapping.items()}
