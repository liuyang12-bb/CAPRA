"""Minimal instance-local Sia smart adapter. Vendored source stays byte-identical."""
import time
import numpy as np
from .upstream import SiaPolicy

ENGINE='sia_smart_adapted_v1'

class SignedCapacity(np.ndarray):
    def __new__(cls,values):
        out=np.asarray(values,dtype=np.int64).copy().view(cls)
        out.upper=np.asarray(values,dtype=np.int64).copy()
        assert np.all(out>=0)
        return out
    def __array_finalize__(self,other):
        self.upper=getattr(other,'upper',None)
    def __setitem__(self,index,value):
        assert np.all(np.asarray(value)>=0),'SMART_SIGNED_UNDERFLOW'
        assert np.all(np.asarray(value)<=self.upper[index]),'SMART_SIGNED_OVERFLOW'
        super().__setitem__(index,value)

class SmartPolicy(SiaPolicy):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.smart_placement=True
        self.smart_records=[]
        self.mip_calls=0
    def optimize_mip(self,*args,**kwargs):
        self.mip_calls+=1
        return super().optimize_mip(*args,**kwargs)
    def alloc_to_placement(self,cluster_name,job_allocs,prev_allocs,node_remaining_gpus):
        began=time.perf_counter()
        cap=SignedCapacity(node_remaining_gpus)
        assert len(cap)>0 and len(set(int(x) for x in cap))==1 and int(cap[0])>0
        positive={k:v for k,v in job_allocs.items() if v[1]>0}
        assert all(v[0]==1 and v[1] in (1,2,4,8) and v[1]<=int(cap[0]) for v in positive.values()),'SMART_DOMAIN'
        self.evicted=[]
        out=self.alloc_to_placement_smart(cluster_name,positive,prev_allocs,cap) if positive else {}
        out.update({k:[] for k,v in job_allocs.items() if v[1]==0})
        use=np.zeros(len(cap),dtype=np.int64)
        assert set(out)==set(job_allocs),'SMART_JOB_SET'
        for k,ids in out.items():
            assert isinstance(ids,list) and len(ids)==job_allocs[k][1],'SMART_COUNT'
            assert not ids or len(set(ids))==1,'SMART_SINGLE_NODE'
            for nid in ids:
                assert 0<=nid<len(use),'SMART_NODE_ID'
                use[nid]+=1
        assert np.all(use<=cap.upper) and np.array_equal(cap.upper-use,np.asarray(cap)),'SMART_CAPACITY'
        preservable=[k for k,v in positive.items() if prev_allocs.get(k,(None,[]))[0]==cluster_name and len(prev_allocs[k][1])==v[1]]
        self.smart_records.append(dict(cluster=cluster_name,gpu_allocations={k:dict(nodes=int(v[0]),gpus=int(v[1])) for k,v in job_allocs.items()},
            prev_placements={k:dict(cluster=v[0],nodes=list(v[1])) for k,v in prev_allocs.items()},initial_capacity=cap.upper.tolist(),remaining_capacity=np.asarray(cap).tolist(),
            raw_smart_plan={k:list(v) for k,v in out.items()},preservable=preservable,evicted=list(self.evicted),
            retained=[k for k in preservable if k not in self.evicted and list(out[k])==list(prev_allocs[k][1])],
            replaced=[k for k in positive if k not in preservable or k in self.evicted],raw_valid=True,sort_fix=True,signed_capacity=True,smart_seconds=time.perf_counter()-began))
        return out

    def alloc_to_placement_smart(self, cluster_name, job_allocs, prev_allocs, node_remaining_gpus):
        # print(f"Cluster: {cluster_name}")
        # print(f"Allocs: {job_allocs}")
        # print(f"Prev Placements: {job_allocs}")
        max_num_nodes = len(node_remaining_gpus)
        # determined {jobname : [gpu0, gpu1, gpu2...]}
        placed_jobs = dict()
        # partition into distributed and single-node jobs
        single_node_jobs, distributed_jobs = [], []
        ngpus_per_node = max(node_remaining_gpus)
        for jobname, (nnodes, ngpus) in job_allocs.items():
            if ngpus >= ngpus_per_node:
                distributed_jobs.append(jobname)
            else:
                single_node_jobs.append(jobname)
        # preserve placements for no change in alloc
        distr_placed_jobs = dict()
        single_placed_jobs = dict()
        for jobname in job_allocs.keys():
            prev_cluster, prev_gpus = prev_allocs.get(jobname, (None, []))
            cur_nnodes, cur_ngpus = job_allocs.get(jobname, (0, 0))
            if prev_cluster == cluster_name and len(prev_gpus) == cur_ngpus:
                if cur_ngpus < ngpus_per_node:
                    single_placed_jobs[jobname] = prev_gpus
                else:
                    distr_placed_jobs[jobname] = prev_gpus
                for node_id in prev_gpus:
                    node_remaining_gpus[node_id] -= 1
                # print(f"Preserving placement: {jobname} -> {cluster_name}, {prev_gpus}")

        # alloc any other distr jobs from last node ID
        for jobname in distributed_jobs:
            # skip if preserving placement
            if jobname in distr_placed_jobs:
                continue
            nnodes, ngpus = job_allocs.get(jobname, (0, 0))
            assert ngpus != 0, f"got zero gpus for {jobname}"
            # allocate nodes from last node ID
            cur_node_id = max_num_nodes - 1
            job_placement = []
            while nnodes > 0 and cur_node_id >= 0:
                # take whole node
                if node_remaining_gpus[cur_node_id] == ngpus_per_node:
                    job_placement.extend([int(cur_node_id)] * ngpus_per_node)
                    node_remaining_gpus[cur_node_id] = 0
                    nnodes -= 1
                cur_node_id -= 1
                if cur_node_id == -1 and nnodes > 0:
                    # reclaim some node from single-node jobs
                    reclaim_node_id = np.argmax(node_remaining_gpus)
                    # print(f"reclaiming node --> {reclaim_node_id}, remaining gpus = {node_remaining_gpus[reclaim_node_id]}")
                    # find jobs mapped to this node
                    reclaim_jobs = []
                    for reclaim_jobname in single_placed_jobs.keys():
                        if reclaim_node_id in single_placed_jobs[reclaim_jobname]:
                            reclaim_jobs.append(reclaim_jobname)
                    for reclaim_jobname in reclaim_jobs:
                        gpus = single_placed_jobs.pop(reclaim_jobname)
                        self.evicted.append(reclaim_jobname)
                        # print(f"evicting {reclaim_jobname} -> {gpus}")
                        for gpu_id in gpus:
                            node_remaining_gpus[gpu_id] += 1
                    assert node_remaining_gpus[reclaim_node_id] == ngpus_per_node, "eviction assert"
                    # loop again to find this freed machine
                    cur_node_id = max_num_nodes - 1
            # ensure all nodes got placed
            assert nnodes == 0, f"couldnt place -- {jobname} -> {job_allocs[jobname]}"
            distr_placed_jobs[jobname] = job_placement
        # print(f"Distributed placements: {distr_placed_jobs}")

        # alloc any single node jobs from first node ID
        def get_job_order(joblist):
            return sorted(joblist, key=lambda x: job_allocs.get(x, (0, 0))[1], reverse=True)
        joblist = [
            jobname for jobname in single_node_jobs if jobname not in single_placed_jobs]
        # priority queue with prio = ngpus
        job_order = get_job_order(joblist)
        while len(job_order) > 0:
            jobname = job_order.pop(0)
            nnodes, ngpus = job_allocs.get(jobname, (0, 0))
            if ngpus == 0:
                single_placed_jobs[jobname] = None
                continue

            # allocate nodes from first node ID
            # prefer packing --> seek node id with min(ngpus) remaining after alloc
            job_placement = []
            idxs = np.arange(max_num_nodes)
            filter = node_remaining_gpus >= ngpus
            if not any(filter):
                # reclaim some gpus by evicting fewest gpus
                reclaim_cand_idxs = idxs[node_remaining_gpus < ngpus]
                reclaim_ordering = sorted(
                    reclaim_cand_idxs, key=lambda x: (ngpus - node_remaining_gpus[x]))
                reclaim_node_id = reclaim_ordering[0]
                # evict some jobs from this node
                # print(f"reclaiming node --> {reclaim_node_id}")
                # find jobs mapped to this node
                reclaim_jobs = []
                for reclaim_jobname in single_placed_jobs.keys():
                    if reclaim_node_id in single_placed_jobs[reclaim_jobname]:
                        reclaim_jobs.append(reclaim_jobname)
                # sort from smallest to largest job in node
                reclaim_jobs = sorted(
                    reclaim_jobs, key=lambda x: job_allocs[x][1])
                while node_remaining_gpus[reclaim_node_id] < ngpus:
                    reclaim_jobname = reclaim_jobs.pop(0)
                    gpus = single_placed_jobs.pop(reclaim_jobname)
                    self.evicted.append(reclaim_jobname)
                    # print(f"evicting {reclaim_jobname} -> {gpus}")
                    for gpu_id in gpus:
                        node_remaining_gpus[gpu_id] += 1
                    # add back to placement queue
                    job_order.append(reclaim_jobname)
                # update placement queue with priorities
                job_order = get_job_order(job_order)
                # print(f"new job order -> {job_order}")
                assert node_remaining_gpus[reclaim_node_id] >= ngpus, "eviction assert"
                filter = node_remaining_gpus >= ngpus
            assert any(
                filter), "failed to find a node to place: {jobname}; allocs = {job_allocs}, prev_allocs = {prev_allocs}, node_remaining_gpus = {node_remaining_gpus}"
            # simple packing algo -- most full valid placement
            place_idxs = idxs[filter]
            place_idxs = sorted(
                place_idxs, key=lambda x: node_remaining_gpus[x])
            place_idx = place_idxs[0]
            job_placement.extend([int(place_idx)] * ngpus)
            node_remaining_gpus[place_idx] -= ngpus
            single_placed_jobs[jobname] = job_placement
        # print(f"Single node placements: {single_placed_jobs}")
        placed_jobs = distr_placed_jobs
        placed_jobs.update(single_placed_jobs)
        return placed_jobs
