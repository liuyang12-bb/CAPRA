"""One acyclic source archive and fixed twelve actual cells before cell 1."""
import zipfile
from r4_utils import *
from capra.methods_r4 import spec,engine
def main():
    check_budget();assert load(DEV/'validation_receipt.json')['status']=='PASS'
    protected=load(DEV/'protected_base.json')
    for p,h in protected.items():assert sha(ROOT/p)==h,('HISTORY_CHANGED',p)
    cells=[];i=0
    for w in (7,8):
        for profile in ('original','cm'):
            methods=('SIA-SMART-P','CAPRA-FK','CAPRA') if w==7 else ('CAPRA','CAPRA-FK','SIA-SMART-P')
            for method in methods:
                i+=1;mode='none' if method=='SIA-SMART-P' else 'ram_slack_v1';work=f'saturn{w}_dense05';inp=f'data/pressure_r4/{work}.csv';cluster='data/scenarios_r1/cluster_cpu3.json';response=f'data/scenarios_r1/responses_{profile}.json'
                cells.append(dict(index=i,scenario=work+'_'+profile,workload_id=work,source_workload_id=f'saturn{w}_supported80',profile=profile,method=method,display_method='CAPRA-FKR' if method=='CAPRA' else method,placement_engine=engine(method),**spec(method,mode),input=inp,cluster=cluster,responses=response,input_hashes={k:sha(ROOT/p) for k,p in [('input',inp),('cluster',cluster),('responses',response)]},output=f'runs/pressure_r4/CAPRA_V2_PRESSURE_R4/{work}_{profile}/{method}',execution_required=True,result_origin='NEW_EXECUTION'))
    assert len(cells)==12
    files=[]
    for b in ('src','third_party','tests'):
        files += [p for p in (ROOT/b).rglob('*') if p.is_file() and '__pycache__' not in p.parts and '.git' not in p.parts]
    files += list((ROOT/'scripts').glob('*r4.py'))+[ROOT/'scripts/scenario_control.py']
    files += [ROOT/p for p in ('pyproject.toml','requirements.lock.txt','requirements_v2.lock.txt','docs/CAPRA_R4_DESIGN.md','docs/CAPRA_R4_EXECUTION_ORDER.txt','docs/CAPRA_R3_SMART_PROVENANCE.json','docs/CAPRA_R3_SMART.patch','data/pressure_r4/generate.py','data/pressure_r4/provenance.json','data/holdout_r3/provenance.json')]
    files += [p for p in (ROOT/'data/pressure_r4').glob('*.provenance.json')]
    files += [ROOT/c[k] for c in cells for k in ('input','cluster','responses')]+[ROOT/f'data/holdout_r3/saturn{w}_supported80.csv' for w in (7,8)]
    files += [DEV/'environment.json',DEV/'closed_loop_control.json',DEV/'offline_validation_receipt.json'];files=sorted(set(files))
    hashes={p.relative_to(ROOT).as_posix():sha(p) for p in files};snapshot=RUN/'source_snapshot.zip';assert not snapshot.exists()
    with zipfile.ZipFile(snapshot,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,p.relative_to(ROOT).as_posix())
        z.writestr('R4_SOURCE_HASHES.json',__import__('json').dumps(dict(base_commit=BASE,files_sha256=hashes),indent=2))
    digest=sha(snapshot);mp=ROOT/'configs/experiment_manifest_pressure_r4.json';assert not mp.exists()
    manifest=dict(version='CAPRA_V2_PRESSURE_R4',base_commit=BASE,frozen_utc=datetime.now(timezone.utc).isoformat(),source_snapshot=snapshot.relative_to(ROOT).as_posix(),source_snapshot_sha256=digest,files_sha256=hashes,protected_sha256=protected,cells=cells,environment=load(DEV/'environment.json'),seed=0,interval=60,horizon=180,wall_limit=900,process_limit=960,max_rounds=6000,total_budget_seconds=10800,cleanup_reserve_seconds=30,shared_budget='runs/pressure_r4/budget_ledger.json',all_cell_order=list(range(1,13)),actual_executions_required=12,equivalence_reuse=False,formal_retries=0,no_remote_push=True,diagnostic_limits=dict(max_states=8,max_jobs=6,max_unlocked=4,max_layouts_per_state=16,max_total_layouts=128,selection='Per condition first E-positive un-covered/no-gross small state and first R-selected small state; dedup; no replacements',diagnostics_within_shared_budget=True),method_semantics_source='R3 unchanged; only new read-only timers',progress_stop='same original STOP_REQUEST/all-arrived30-stagnant/3x30s')
    dump(mp,manifest)
    with zipfile.ZipFile(snapshot) as z:
        for p,h in hashes.items():assert __import__('hashlib').sha256(z.read(p)).hexdigest()==h
    for c in cells:c.update(base_commit=BASE,phase_version=manifest['version'],manifest=mp.relative_to(ROOT).as_posix(),manifest_sha256=sha(mp),source_snapshot_sha256=digest)
    dump(RUN/'matrix_index.json',cells);dump(RUN/'matrix_ledger.json',dict(cells=[dict(index=c['index'],state='CREATED',output=c['output'],executed=False) for c in cells]))
    dump(RUN/'freeze_receipt.json',dict(base_commit=BASE,source_snapshot_sha256=digest,manifest_sha256=sha(mp),manifest=mp.relative_to(ROOT).as_posix(),frozen_files=len(hashes),protected_files=len(protected),physical_cells=12,archive_verified=True))
    record('freeze',status='PASS',frozen_files=len(hashes),physical_cells=12);print('R4_FROZEN_TWELVE_ACTUAL_CELLS')
if __name__=='__main__':main()
