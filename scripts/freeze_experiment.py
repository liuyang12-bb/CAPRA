"""Must run before any main result; no parameter selection from main outcomes."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
target=ROOT/'configs/experiment_manifest.json'
assert not target.exists()
provenance=json.loads((ROOT/'data/provenance.json').read_text())
pilot=json.loads((ROOT/'runs/validation/capra_pilot_01/summary.json').read_text())
cells=[]
for w in provenance['workloads']:
    label=Path(w['input']).stem
    for method in ('SIA-P','CAPRA-Fixed','CAPRA'):
        cells.append(dict(workload=label,method=method,input=w['input'],input_sha256=w['sha256'],output=f'runs/main_v1/{label}/{method}'))
files=[]
for base in ('src','scripts','tests','third_party'):
    files.extend(p for p in (ROOT/base).rglob('*') if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts)
files.extend([ROOT/'pyproject.toml',ROOT/'requirements.lock.txt',ROOT/'configs/cluster.json',ROOT/'data/responses.json',ROOT/'data/provenance.json'])
manifest=dict(project='CAPRA',version='0.1.0',frozen_utc=datetime.now(timezone.utc).isoformat(),
    code_commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),
    sources=json.loads((ROOT/'docs/upstream_versions.json').read_text()),source_sha256={str(p.relative_to(ROOT)):sha(p) for p in sorted(files)},
    cells=cells,workload_selection=provenance['workloads'],topology=json.loads((ROOT/'configs/cluster.json').read_text()),
    responses_sha256=sha(ROOT/'data/responses.json'),python='3.10.10',seed=0,python_hash_seed=0,numeric_threads=1,
    gpu_domain={'aws':[1,2,4],'dgx-ext':[1,2,4,8],'rtx':[1,2,4,8]},single_node_per_job=True,
    batch='Official Sia Job.update_local_bsz, online adaptation; no stage-two batch search',gpu_profiles='Official online model plus Sia projection; no preseed/full oracle model',
    interval=60,max_rounds=6000,runner_wall_limit_seconds=900,external_process_wall_limit_seconds=960,
    stop_rules=['USER_STOP file','30 rounds with no aggregate training progress after all arrivals','3 successive active decisions over 30s','wall/round limit'],
    migration='Node identity OR GPU type OR GPU count change, application rescale time; same-type node migration charged; aux-only changes zero cost; exact restore lock',
    overhead='Complete decision from job-info construction through GPU solve, profile, placement, quotas, validation and commit; reported separately, not charged to simulated time. Grid wall includes child imports and audits.',
    quantiles='numpy.quantile linear interpolation, all jobs; JCT=completion-arrival; makespan=last completion-first arrival; no completed-subset aggregate when censored',
    pilot=dict(output='runs/validation/capra_pilot_01',rounds=pilot['rounds'],completed=pilot['completed'],total=pilot['total'],wall_seconds=pilot['wall_seconds'],decision_median=pilot['decision_median'],decision_max=pilot['decision_max']),
    estimate='12-job 80-round pilot took 33.37s, active decision median 0.0228s/max 0.0984s. Arrival spans 20,088/22,112s imply >=335/369 rounds at 60s. Rough 3-10 minutes per main cell allowing more active jobs, training fits and longer tails; hard 15-min runner and 16-min process cap. Estimate is not a completion guarantee.',
    exclusions=['No old MELD/SIA-AUX/other excluded comparison','No new ETA/search/swaps','No workload/profile retuning after main outcomes','No remote repository or push'],
    order='First workload three cells and small table, then second workload three cells. No automatic expansion. On correctness failure stop remainder with explicit NOT_RUN records.')
target.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(manifest=str(target),sha256=sha(target),cells=len(cells),frozen_files=len(files)),ensure_ascii=False))
