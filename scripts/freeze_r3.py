"""Freeze all 15 physical cells and four conditional aliases before A1."""
import zipfile
from r3_utils import *
from capra.methods_r3 import spec,engine
def main():
    check_budget();assert load(DEV/'validation_receipt.json')['status']=='PASS'
    protected=load(DEV/'protected_base.json')
    for p,h in protected.items():assert sha(ROOT/p)==h,('HISTORY_CHANGED',p)
    versions={'A':'CAPRA_V2_SMART_R3','B':'CAPRA_V2_HOLDOUT_R3'}
    old={x['id']:x for x in load(ROOT/'configs/scenarios_r1.json')['scenarios']}
    specs=[('A','w2_dense','original','SIA-SMART-P'),('A','w2_dense','CM','SIA-SMART-P'),('A','w6_dense','original','SIA-SMART-P')]
    specs += [('B','saturn7_supported80','original',m) for m in ('SIA-SMART-P','SIA-P-K','CAPRA-FK','CAPRA')]
    specs += [('B','saturn7_supported80','CM',m) for m in ('CAPRA-FK','CAPRA')]
    specs += [('B','saturn8_supported80','original',m) for m in ('CAPRA','CAPRA-FK','SIA-P-K','SIA-SMART-P')]
    specs += [('B','saturn8_supported80','CM',m) for m in ('CAPRA','CAPRA-FK')]
    cells=[]
    for i,(phase,work,profile,method) in enumerate(specs,1):
        mode='none' if method in ('SIA-SMART-P','SIA-P-K') else 'ram_slack_v1'
        inp=f'data/scenarios_r1/{work}.csv' if phase=='A' else f'data/holdout_r3/{work}.csv'
        scenario=work+'_'+profile.lower();cl='data/scenarios_r1/cluster_cpu3.json';rp='data/scenarios_r1/responses_'+profile.lower()+'.json'
        cells.append(dict(index=i,phase=phase,phase_version=versions[phase],scenario=scenario,workload_id=work,profile=profile,method=method,placement_engine=engine(method),**spec(method,mode),input=inp,cluster=cl,responses=rp,input_hashes={k:sha(ROOT/p) for k,p in [('input',inp),('cluster',cl),('responses',rp)]},output=f'runs/smart_holdout_r3/{versions[phase]}/{scenario}/{method}',executed=True,result_origin='NEW_EXECUTION'))
    assert len(cells)==15
    aliases=[]
    for i,source in enumerate((4,5,13,12),16):
        c=cells[source-1];aliases.append(dict(index=i,phase='B',scenario=c['workload_id']+'_cm',workload_id=c['workload_id'],profile='CM',method=c['method'],source_physical_index=source,executed=False,result_origin='EQUIVALENCE_REUSED',source_profile='original',target_profile='CM',target_profile_sha256=sha(ROOT/'data/scenarios_r1/responses_cm.json'),source_profile_sha256=sha(ROOT/'data/scenarios_r1/responses_original.json'),equivalence_gate='strict proportional points/static induction/R2 P-K/A smart control/source complete audit',timing_scope='source original observed/reused; not measured in CM'))
    files=[]
    for b in ('src','third_party','tests'):
        files += [p for p in (ROOT/b).rglob('*') if p.is_file() and '__pycache__' not in p.parts and '.git' not in p.parts]
    files += list((ROOT/'scripts').glob('*r3.py'))+[ROOT/'scripts/scenario_control.py']
    files += [ROOT/p for p in ('pyproject.toml','requirements.lock.txt','requirements_v2.lock.txt','docs/CAPRA_R3_DESIGN.md','docs/CAPRA_R3_BASELINE_SPEC.md','docs/CAPRA_R3_EXECUTION_ORDER.txt','docs/CAPRA_R3_SMART_PROVENANCE.json','docs/CAPRA_R3_SMART.patch','docs/CAPRA_R3_SMART_SOURCE.py.txt','data/holdout_r3/provenance.json')]
    files += [ROOT/c[k] for c in cells for k in ('input','cluster','responses')]
    files += [DEV/'environment.json',DEV/'equivalence_static_certificate.json',DEV/'proportional_points.json',DEV/'r2_pk_control.json']
    files=sorted(set(files));hashes={p.relative_to(ROOT).as_posix():sha(p) for p in files}
    snapshot=RUN/'source_snapshot.zip';assert not snapshot.exists()
    with zipfile.ZipFile(snapshot,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,p.relative_to(ROOT).as_posix())
        z.writestr('R3_SOURCE_HASHES.json',__import__('json').dumps(dict(base_commit=BASE,files_sha256=hashes),indent=2))
    snapshotsha=sha(snapshot);mh={}
    for phase,name in [('A','smart'),('B','holdout')]:
        mp=ROOT/f'configs/experiment_manifest_{name}_r3.json';assert not mp.exists()
        m=dict(version=versions[phase],phase=phase,base_commit=BASE,frozen_utc=datetime.now(timezone.utc).isoformat(),source_snapshot=snapshot.relative_to(ROOT).as_posix(),source_snapshot_sha256=snapshotsha,files_sha256=hashes,protected_sha256=protected,cells=[c for c in cells if c['phase']==phase],all_cell_order=list(range(1,16)),logical_aliases=aliases,environment=load(DEV/'environment.json'),seed=0,interval=60,horizon=180,wall_limit=900,process_limit=960,max_rounds=6000,total_budget_seconds=7200,shared_budget='runs/smart_holdout_r3/budget_ledger.json',cleanup_reserve_seconds=30,formal_retries=0,stop_on_failure=True,no_remote_push=True,equivalence_exclusions=load(DEV/'r2_pk_control.json')['excluded_exact_keys'])
        dump(mp,m);mh[mp.relative_to(ROOT).as_posix()]=sha(mp)
        for c in cells:
            if c['phase']==phase:c['manifest']=mp.relative_to(ROOT).as_posix();c['manifest_sha256']=sha(mp);c['source_snapshot_sha256']=snapshotsha;c['base_commit']=BASE
    with zipfile.ZipFile(snapshot) as z:
        for p,h in hashes.items():assert __import__('hashlib').sha256(z.read(p)).hexdigest()==h
    dump(RUN/'matrix_index.json',cells);dump(RUN/'logical_reuse_registration.json',aliases)
    dump(RUN/'freeze_receipt.json',dict(base_commit=BASE,source_snapshot_sha256=snapshotsha,manifests_sha256=mh,frozen_files=len(hashes),protected_files=len(protected),archive_verified=True,physical_cells=15,logical_aliases=4))
    record('freeze_both_phases',status='PASS',frozen_files=len(hashes),source_snapshot_sha256=snapshotsha)
    print('R3_BOTH_PHASES_FROZEN',flush=True)
if __name__=='__main__':main()
