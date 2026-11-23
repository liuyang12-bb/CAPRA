"""Both phases frozen before first formal cell; one source archive, no self hashes."""
import subprocess,zipfile,platform
from datetime import datetime,timezone
from r2_utils import *
from capra.methods_r2 import spec
def main():
    check_budget();assert load(DEV/'validation_receipt.json')['status']=='PASS'
    targets=[ROOT/'configs/experiment_manifest_ablation_r2.json',ROOT/'configs/experiment_manifest_ram_r2.json']
    assert all(not p.exists() for p in targets)
    protected=load(DEV/'protected_base.json')
    for p,h in protected.items():assert sha(ROOT/p)==h,('HISTORY_CHANGED',p)
    scenarios={x['id']:x for x in load(ROOT/'configs/scenarios_r1.json')['scenarios']};original=load(ROOT/'configs/experiment_manifest_scenarios_r1.json')
    specs=[('A','w2_dense_original','SIA-P-K','none'),('A','w2_dense_original','CAPRA-FK','legacy'),('A','w6_dense_original','SIA-P-K','none'),('A','w6_dense_original','CAPRA-FK','legacy'),('A','w2_dense_cm','SIA-P-K','none'),('A','w2_dense_cm','CAPRA-FK','legacy'),('B','w2_dense_cm','CAPRA-Fixed','ram_slack_v1'),('B','w2_dense_cm','CAPRA-FK','ram_slack_v1'),('B','w2_dense_cm','CAPRA','ram_slack_v1')]
    versions={'A':'CAPRA_V2_ABLATION_R2','B':'CAPRA_V2_RAM_R2'};cells=[]
    for index,(phase,scenario,method,mode) in enumerate(specs,1):
        c=scenarios[scenario]
        for field in ('input','cluster','responses'):assert sha(ROOT/c[field])==original['files_sha256'][c[field]]
        cells.append(dict(index=index,phase=phase,phase_version=versions[phase],scenario=scenario,method=method,**spec(method,mode),input=c['input'],cluster=c['cluster'],responses=c['responses'],
            input_hashes={field:sha(ROOT/c[field]) for field in ('input','cluster','responses')},output=f'runs/ablation_ram_r2/{versions[phase]}/{scenario}/{method}'))
    files=[]
    for base in ('src','third_party','tests'):
        files.extend(p for p in (ROOT/base).rglob('*') if p.is_file() and '__pycache__' not in p.parts and '.git' not in p.parts)
    files+=list((ROOT/'scripts').glob('*r2.py'))+[ROOT/'scripts/scenario_control.py',ROOT/'scripts/r2_utils.py']
    files+=[ROOT/p for p in ('pyproject.toml','requirements.lock.txt','requirements_v2.lock.txt','docs/CAPRA_R2_DESIGN.md','docs/CAPRA_R2_EXECUTION_ORDER.txt','configs/scenarios_r1.json')]
    files+=[ROOT/c[field] for c in cells for field in ('input','cluster','responses')];files+=[DEV/'environment.json'];files=sorted(set(files))
    hashes={p.relative_to(ROOT).as_posix():sha(p) for p in files};snapshot=RUN/'source_snapshot.zip';assert not snapshot.exists()
    with zipfile.ZipFile(snapshot,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,p.relative_to(ROOT).as_posix())
        z.writestr('R2_SOURCE_HASHES.json',__import__('json').dumps(dict(base_commit=BASE,files_sha256=hashes),indent=2))
    snapshotsha=sha(snapshot);manifest_hashes={}
    for phase,target in zip(('A','B'),targets):
        version=versions[phase];out=RUN/version;out.mkdir(exist_ok=False)
        m=dict(version=version,phase=phase,base_commit=BASE,frozen_utc=datetime.now(timezone.utc).isoformat(),source_snapshot=snapshot.relative_to(ROOT).as_posix(),source_snapshot_sha256=snapshotsha,
            files_sha256=hashes,protected_sha256=protected,cells=[c for c in cells if c['phase']==phase],all_cell_order=[c['index'] for c in cells],
            environment=load(DEV/'environment.json'),seed=0,interval=60,horizon=180,wall_limit=900,process_limit=960,max_rounds=6000,total_budget_seconds=5400,
            shared_budget='runs/ablation_ram_r2/budget_ledger.json',cleanup_reserve_seconds=30,ram_rule='post-original-final-solution;axis+true-upper;priority12;EPS1e-9;bound remaining-axis-count+1',
            formal_retries=0,stop_on_failure=True,scheduling_wall_charged_to_JCT=False,recovery_charged_to_JCT=True,no_remote_push=True)
        dump(target,m);manifest_hashes[target.relative_to(ROOT).as_posix()]=sha(target)
    with zipfile.ZipFile(snapshot) as z:
        for p,h in hashes.items():assert __import__('hashlib').sha256(z.read(p)).hexdigest()==h
    from capra.inputs import describe
    index=[]
    for c in cells:
        mp=next(p for p in manifest_hashes if ('ablation' in p)==(c['phase']=='A'))
        old_start=load(ROOT/f'runs/scenarios_r1/CAPRA_V2_SCENARIOS_R1/{c["scenario"]}/SIA-P/start.json')
        index.append(dict(c,base_commit=BASE,source_snapshot_sha256=snapshotsha,manifest_sha256=manifest_hashes[mp],manifest=mp,
            inputs={kind:describe(ROOT/c[key]) for kind,key in (('workload','input'),('cluster','cluster'),('responses','responses'))},
            seed=0,interval=60,horizon=180,environment=load(DEV/'environment.json'),costs=old_start['costs'],runner_limit=900,process_limit=960,max_rounds=6000))
    dump(RUN/'matrix_index.json',index);dump(RUN/'freeze_receipt.json',dict(base_commit=BASE,source_snapshot_sha256=snapshotsha,manifests_sha256=manifest_hashes,frozen_files=len(hashes),protected_files=len(protected),archive_verified=True))
    record('freeze_both_phases',status='PASS',frozen_files=len(hashes),source_snapshot_sha256=snapshotsha)
    print('R2_BOTH_PHASES_FROZEN',flush=True)
if __name__=='__main__':main()
