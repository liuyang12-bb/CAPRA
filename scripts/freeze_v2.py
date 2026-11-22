"""Freeze after validation, before all six v2 cells. Never overwrite v1 or v2."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
target=ROOT/'configs/experiment_manifest_v2.json'
assert not target.exists()
protected=json.loads((ROOT/'runs/capra_v2/development/protected_v1.json').read_text())
for name,digest in protected['sha256'].items():assert sha(ROOT/name)==digest,('V1_PROTECTED',name)
v1=json.loads((ROOT/'configs/experiment_manifest.json').read_text())
for name in ('configs/cluster.json','data/responses.json'):
    assert sha(ROOT/name)==v1['source_sha256'][name.replace('/',chr(92))],('INPUT_CHANGED',name)
cells=[]
version='CAPRA_V2_R1'
for w in v1['workload_selection']:
    assert sha(ROOT/w['input'])==w['sha256']
    for method in ('SIA-P','CAPRA-Fixed','CAPRA'):
        label=Path(w['input']).stem
        cells.append(dict(workload=label,method=method,input=w['input'],input_sha256=w['sha256'],output=f'runs/capra_v2/{version}/{label}/{method}'))
files=[]
for base in ('src','scripts','tests','third_party'):
    files.extend(p for p in (ROOT/base).rglob('*') if p.is_file() and '__pycache__' not in p.parts and '.git' not in p.parts)
files.extend(ROOT/x for x in ('pyproject.toml','requirements.lock.txt','requirements_v2.lock.txt','configs/cluster.json','data/responses.json','data/provenance.json'))
files.extend(ROOT/c['input'] for c in cells)
files=sorted(set(files))
head=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
assert not subprocess.check_output(['git','-C',str(ROOT),'diff','HEAD','--','src','scripts','tests','third_party','requirements_v2.lock.txt']).strip(),'COMMIT_RUNTIME_BEFORE_FREEZE'
pilot=json.loads((ROOT/'runs/capra_v2/development/pilot_01/summary.json').read_text(encoding='utf8'))
assert pilot['v2_raw_audit']=='PASS'
manifest=dict(version=version,frozen_utc=datetime.now(timezone.utc).isoformat(),code_commit=head,base_commit=protected['base_commit'],
    files_sha256={str(p.relative_to(ROOT)):sha(p) for p in files},protected_v1=protected,
    cells=cells,interval=60,max_rounds=6000,wall_limit=900,process_limit=960,total_budget_seconds=7200,
    mechanism_validation_budget_reserve_seconds=60,optional_ablation=False,optional_ablation_reason='Not preregistered; exactly six formal cells',
    response='Unchanged v1 table, interpolation, normalization and transfer assumptions; explicit minimum range',
    cost_source='Actual Application.rescale_time table; v2 Sia restart_costs and costs.py/commit_v2 share it',
    common='Equivalent-node identity or whole swap, exact locks, canonical idempotent ties; Sia p=-0.5/objective unchanged except shared restart prediction cost',
    horizon=180,epsilon=1e-9,capacity_epsilon=1e-7,coordinate_decimals=8,priority_decimals=12,initial_rho_decimals=10,
    cpu_granularity='1 total core',ram_points='profile*GPU, exact proportional, compatible current, one baseline capacity boundary',
    maximum_initial_vectors_per_node=2,maximum_layouts=3,layout_order=['F','K','R'],selection='phi, total delay, GPU/physical changes, F/K/R',
    reorder='full-node or unique-feasible first; pressure descending; GPUs descending; job name; marginal total node rho then current node/delay/nodeID',
    frozen_design_sha256=sha(ROOT/'docs/CAPRA_V2_DESIGN.md'),dependencies_sha256=sha(ROOT/'requirements_v2.lock.txt'),
    numeric_environment=dict(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONHASHSEED='0'),seed=0,
    solver='CVXPY 1.6.5 SCIPY/HiGHS (SciPy 1.13.1), time_limit=10, mip_rel_gap=1e-4',
    scheduling_wall_charged_to_JCT=False,recovery_charged_to_JCT=True,
    stop_rules=['900-second simulator','960-second owned child tree','6000 rounds','30 rounds no progress after all arrivals','3 active decisions >30s','STOP_REQUEST','cumulative 7200s incl pilot/failures/reserve','audit failure stops subsequent cells'],
    pilot=dict(wall_seconds=pilot['wall_seconds'],rounds=80,complete=pilot['completed'],total=12,decision_median=pilot['decision_median'],decision_max=pilot['decision_max']),
    estimate='80-round/12-job pilot process36.92s, whole-decision median0.0239/max0.112s. Expect roughly3-10min/cell with original arrivals and tails; limits are not completion guarantees.',
    no_parameter_tuning=True,no_remote_push=True)
target.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
run=ROOT/'runs/capra_v2'/version;run.mkdir(exist_ok=False)
archive=run/'frozen_source.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in files:z.write(p,p.relative_to(ROOT))
    for p in (target,ROOT/'docs/CAPRA_V2_DESIGN.md'):z.write(p,p.relative_to(ROOT))
with zipfile.ZipFile(archive) as z:
    for name,digest in manifest['files_sha256'].items():assert hashlib.sha256(z.read(name.replace(chr(92),'/'))).hexdigest()==digest
(run/'freeze_receipt.json').write_text(json.dumps(dict(version=version,code_commit=head,manifest_sha256=sha(target),source_zip_sha256=sha(archive),frozen_files=len(files),v1_unchanged=True),indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(version=version,manifest=str(target),code_commit=head,files=len(files),archive=str(archive)),ensure_ascii=False))
