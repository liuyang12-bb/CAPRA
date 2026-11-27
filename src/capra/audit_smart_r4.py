"""Independent raw-smart/lock-witness checks. No scheduling function imports."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def check_start(start):
    methods={'SIA-SMART-P':'sia_smart_adapted_v1','CAPRA-FK':'sia_fast_original','CAPRA':'sia_fast_original'}
    assert start['method'] in methods and start['placement_engine']==methods[start['method']]
    assert start['version'] in ('CAPRA_V2_PRESSURE_R4','CAPRA_V2_PRESSURE_R4_PREP')
    p=start['smart_provenance']
    for field,file in [('source_file_sha256',p['source_file']),('adapter_file_sha256','src/capra/smart_r3.py'),('patch_sha256','docs/CAPRA_R3_SMART.patch')]:
        assert hashlib.sha256((ROOT/file).read_bytes()).hexdigest()==p[field]
def check_round(r,start,nodes):
    meta=r['gpu_stage'];assert meta['placement_engine']==start['placement_engine']
    if start['method']!='SIA-SMART-P':
        assert not meta.get('smart_records');return
    assert meta['raw_valid'] and meta['mip_calls']==(1 if meta['solver_status']!='NO_JOBS' else 0)
    raw=r['raw_sia_plan'];seen={};usage={k:0 for k in nodes}
    for c in meta['smart_records']:
        assert c['sort_fix'] and c['signed_capacity'] and c['raw_valid']
        assert len(c['initial_capacity'])==len(c['remaining_capacity'])
        use=[0]*len(c['initial_capacity'])
        assert set(c['gpu_allocations'])==set(c['raw_smart_plan'])
        for k,p in c['gpu_allocations'].items():
            ids=c['raw_smart_plan'][k]
            assert len(ids)==p['gpus'] and (not ids or len(set(ids))==1)
            assert p['nodes']==1 and p['gpus'] in (1,2,4,8)
            for idx in ids:assert 0<=idx<len(use);use[idx]+=1
            assert k not in seen
            if ids:seen[k]=dict(gpu_type=c['cluster'],gpus=p['gpus'],node=f"{c['cluster']}:{ids[0]}")
        assert all(0<=u<=n and n-u==left for n,u,left in zip(c['initial_capacity'],use,c['remaining_capacity']))
        for k in c['retained']:
            assert k in c['preservable'] and k not in c['evicted'] and c['raw_smart_plan'][k]==c['prev_placements'][k]['nodes']
    assert seen==raw,'RAW_SMART_GPU_PLAN'
    for k,p in raw.items():
        assert p['gpu_type']==nodes[p['node']]['gpu_type'];usage[p['node']]+=p['gpus']
    assert all(usage[n]<=nodes[n]['gpus'] for n in nodes)
    repaired=r['lock_repaired_gpu_plan'];repairs=meta['repairs'];locks=r['locks']
    if repairs:
        assert len(repairs)==1 and repairs[0]['reason']=='SHARED_PHYSICAL_LOCK_REPAIR' and locks
        assert repairs[0]['before']=={k:p['node'] for k,p in raw.items()}
        witness=meta['same_mip_physical_witness'];assert len(witness)==len({x['job'] for x in witness})
        assert {x['job'] for x in witness}==set(raw)
        for w in witness:
            k=w['job'];assert (w['gpu_type'],w['gpus'])==(raw[k]['gpu_type'],raw[k]['gpus'])
            assert w['node']==repaired[k]['node']==repairs[0]['after'][k]
        # The replacement must have an actual locked physical/auxiliary conflict.
        conflict=any(k not in raw or raw[k]['node']!=a['node'] for k,a in locks.items())
        for nid,n in nodes.items():
            for f in ('cpu','ram'):
                total=sum(locks[k][f] if k in locks else n[f]*p['gpus']/n['gpus'] for k,p in raw.items() if p['node']==nid)
                conflict=conflict or total>n[f]+1e-7
        assert conflict,'UNJUSTIFIED_SMART_REPAIR'
    else:assert all(repaired[k]['node']==p['node'] for k,p in raw.items()),'MISSING_SMART_REPAIR_RECORD'
