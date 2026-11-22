"""Final integrity manifest after all offline review; no simulations or network."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,time,csv
import numpy as np
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=load(ROOT/'configs/experiment_manifest_v2.json');rows=load(OUT/'results.json')
for n,h in m['files_sha256'].items():assert sha(ROOT/n)==h,('FROZEN_RUNTIME_CHANGED',n)
for n,h in m['protected_v1']['sha256'].items():assert sha(ROOT/n)==h,('HISTORY_CHANGED',n)
freeze=load(OUT/'freeze_receipt.json');assert sha(OUT/'frozen_source.zip')==freeze['source_zip_sha256']
assert len(rows)==6
for r in rows:
    assert r['status']=='ALL_COMPLETE' and r['completed']==80 and r['total']==80
    d=ROOT/r['output']
    for name in ('output_hashes.json','audit_hashes.json'):
        for n,h in load(d/name).items():assert sha(d/n)==h
    per=list(csv.DictReader((d/'per_job.csv').open(encoding='utf8',newline='')))
    assert len(per)==80 and abs(sum(float(p['jct']) for p in per)/80-r['mean_jct'])<1e-7
    for p in per:assert abs(float(p['jct'])-sum(float(p[k]) for k in ('waiting','training','recovery')))<1e-7
    for q,key in ((.5,'p50_jct'),(.95,'p95_jct'),(.99,'p99_jct')):assert abs(np.quantile([float(p['jct']) for p in per],q)-r[key])<1e-7
    assert abs(r['mean_jct']-r['mean_waiting']-r['mean_training']-r['mean_recovery'])<1e-7

# Preserve all pre-v2 README bytes and add only the new section.
readme=ROOT/'README.md';text=readme.read_text(encoding='utf8');section='## CAPRA v2 本地交付\n'+text.split('## CAPRA v2 本地交付\n',1)[1]
base=subprocess.check_output(['git','-C',str(ROOT),'show','1f1f07fd2238b395e108f91dbbc224d07c0c8139:README.md'])
newline='\r\n' if b'\r\n' in base else '\n'
readme.write_bytes(base+newline.encode()+section.replace('\n',newline).encode('utf8'))

first=(ROOT/'.git/logs/refs/heads/capra/v2-20261122').read_text(encoding='utf8').splitlines()[0]
epoch=int(first.split('\t')[0].rsplit(' ',2)[-2]);now=time.time()
v=load(OUT/'final_verification.json');v.update(figure_review_status='PASS: both final PNG figures visually inspected; legend outside data',
    task_wall_since_branch_seconds=now-epoch,sealed_utc=datetime.now(timezone.utc).isoformat(),source_zip_sha256=freeze['source_zip_sha256'],
    independent_final_arithmetic_checks=dict(cells=6,jobs=480,jct_time_identities=480,quantile_checks=18),budget_accounted_seconds=load(ROOT/'runs/capra_v2/budget_ledger.json')['accounted_seconds'])
(OUT/'final_verification.json').write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
report=ROOT/'docs/CAPRA_V2_RESULTS.md'
report.write_text(report.read_text(encoding='utf8')+f'''\n## 最终封存\n\n1030个冻结运行文件及99个v1保护文件再次匹配；六格480个作业JCT时间恒等式和18项分位数复核通过。两张最终PNG已目视检查，PDF同时保留。本地分支创建至封存约{(now-epoch)/60:.2f}分钟，模拟实验23.56分钟；未推送、未启动额外实验。\n\n图表：[均值](../runs/capra_v2/CAPRA_V2_R1/figures/v2_mean_jct.png)、[时间分解](../runs/capra_v2/CAPRA_V2_R1/figures/v2_time_decomposition.png)。最终索引为运行目录`EVIDENCE_INDEX.md`；完整校验清单为`evidence_hashes.json`。\n''',encoding='utf8')
(OUT/'EVIDENCE_INDEX.md').write_text('''# CAPRA v2 evidence

- `results.csv/json`: six same-version cells, 80/80 each, no mixing with v1.
- `saturn-*/{SIA-P,CAPRA-Fixed,CAPRA}/events.jsonl.gz`: full raw events; complete commands in process.json.
- Per cell `summary.json`, `per_job.csv`, `node_resources.csv`, `v2_audit.json`, `output_hashes.json`, `audit_hashes.json`.
- `paired_jobs.csv`: all 160 jobs, all positive/negative paired differences.
- `average_node_allocations.csv`, `supplementary_metrics.json`, `raw_opportunity_analysis.json`, `application_time_and_jct.csv`.
- `v1_historical_reference.csv`: reference only; original v1 files unchanged.
- `frozen_source.zip`, `freeze_receipt.json`: exact runtime source and manifest, code commit 2517e5cd6bfd93f094b728e226478d4cf56cc45f.
- `figures/`: final PNG/PDF; report_revisions/ preserves initial render and report.
- `analysis_tools/`: post-experiment read-only analysis and delivery producers, not runtime algorithm changes.
- `final_verification.json`, `evidence_hashes.json`: final source/history/arithmetic/figure checks.
- Parent development/: pilot raw events and all test logs, including fixture failure and correction.
- Parent budget_ledger.json: pilot+six formal cells 1413.832s, plus60s validation reserve, below7200s limit.

Design/report: docs/CAPRA_V2_DESIGN.md and docs/CAPRA_V2_RESULTS.md.
Manifest: configs/experiment_manifest_v2.json. No remote push, extra cohort, tuning, optional ablation, or deterministic repetition was performed.
''',encoding='utf8')
hashes={str(p.relative_to(ROOT)):sha(p) for p in OUT.rglob('*') if p.is_file() and p.name!='evidence_hashes.json'}
for n in ('docs/CAPRA_V2_RESULTS.md','docs/CAPRA_V2_DESIGN.md','configs/experiment_manifest_v2.json','requirements_v2.lock.txt','runs/capra_v2/budget_ledger.json','README.md','scripts/replay_v2_audit.py'):
    hashes[n]=sha(ROOT/n)
(OUT/'evidence_hashes.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(status='PASS',files=len(hashes),task_minutes=(now-epoch)/60,experimental_minutes=load(ROOT/'runs/capra_v2/budget_ledger.json')['used_seconds']/60,source_files=1030,protected_files=99,remote_push=False),ensure_ascii=False))
