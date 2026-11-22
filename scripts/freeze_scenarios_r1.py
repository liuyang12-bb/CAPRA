"""Freeze the complete scenario runtime, without changing legacy frozen artifacts."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,platform,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf8'))
def main():
    target=ROOT/'configs/experiment_manifest_scenarios_r1.json';assert not target.exists()
    assert load(ROOT/'runs/scenarios_r1/development/validation_receipt.json')['status']=='PASS'
    protected=load(ROOT/'runs/scenarios_r1/development/protected.json')
    for p,h in protected.items():assert sha(ROOT/p)==h,('PROTECTED_CHANGED',p)
    old=load(ROOT/'configs/experiment_manifest_v2.json')
    algorithm={}
    for p,h in old['files_sha256'].items():
        p=p.replace('\\','/')
        if p.startswith('third_party/') or (p.startswith('src/capra/') and Path(p).name not in ('runner_v2.py','audit.py','audit_v2.py')):
            assert sha(ROOT/p)==h,('ALGORITHM_CHANGED_FROM_V2',p);algorithm[p]=h
    config=load(ROOT/'configs/scenarios_r1.json');version='CAPRA_V2_SCENARIOS_R1';cells=[]
    for s in config['scenarios']:
        for method in config['method_order']:
            cells.append(dict(scenario=s['id'],method=method,input=s['input'],cluster=s['cluster'],responses=s['responses'],output=f'runs/scenarios_r1/{version}/{s["id"]}/{method}'))
    files=[]
    for base in ('src','tests','third_party'):
        files.extend(p for p in (ROOT/base).rglob('*') if p.is_file() and '__pycache__' not in p.parts and '.git' not in p.parts)
    files.extend(ROOT/'scripts'/p for p in ('build_scenarios_r1.py','scenario_control.py','validate_scenarios_r1.py','freeze_scenarios_r1.py','run_scenarios_r1.py'))
    files.extend((ROOT/'data/scenarios_r1').glob('*'))
    files.extend(ROOT/p for p in ('configs/scenarios_r1.json','configs/cluster.json','data/responses.json','data/saturn-2-supported80.csv','data/saturn-6-supported80.csv','requirements_v2.lock.txt','requirements.lock.txt','pyproject.toml','docs/SCENARIOS_R1_DESIGN.md','docs/SCENARIOS_R1_EXECUTION_ORDER.txt'))
    files=sorted(set(files));head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    assert head==config['base_commit']
    m=dict(version=version,frozen_utc=datetime.now(timezone.utc).isoformat(),base_commit=head,source_reference='Exact frozen_source.zip including all changed/new runtime files; hashes below',
        files_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in files},algorithm_protected_sha256=algorithm,protected_sha256=protected,cells=cells,
        interval=60,horizon=180,seed=0,max_rounds=6000,wall_limit=900,process_limit=960,total_budget_seconds=7200,cleanup_reserve_seconds=30,
        numeric_environment=old['numeric_environment'],solver=old['solver'],python=platform.python_version(),dependency_lock_sha256=sha(ROOT/'requirements_v2.lock.txt'),
        performance_reference='3CPU/GPU,62.5GB/GPU fixed; floor relative to each scenario proportional allocation',
        cost_source='Unchanged v2 actual application rescale_time',scheduling_wall_charged_to_JCT=False,recovery_charged_to_JCT=True,
        stop_rules=old['stop_rules'],failure_policy='Stop all later cells on audit/execution bug; preserve all failures; new freeze required after correction; do not pool versions',
        retries='No automatic experiment retries registered; environment failures require preserved new directory and same deadline',no_parameter_tuning=True,no_remote_push=True)
    target.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    run=ROOT/'runs/scenarios_r1'/version;run.mkdir(exist_ok=False);archive=run/'frozen_source.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files+[target]:z.write(p,p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:
        for p,h in m['files_sha256'].items():assert hashlib.sha256(z.read(p)).hexdigest()==h
    receipt=dict(version=version,base_commit=head,frozen_files=len(files),algorithm_files=len(algorithm),protected_files=len(protected),manifest_sha256=sha(target),source_zip_sha256=sha(archive),python=platform.python_version())
    (run/'freeze_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8')
    print(json.dumps(receipt))
if __name__=='__main__':main()
