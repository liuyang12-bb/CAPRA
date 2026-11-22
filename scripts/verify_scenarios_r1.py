"""Read-only runtime/history/input integrity + independent one-target certificate checks."""
from pathlib import Path
from datetime import datetime,timezone
import csv,gzip,hashlib,json,subprocess,time,zipfile
from capra.response import Responses
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'runs/scenarios_r1/CAPRA_V2_SCENARIOS_R1'
def load(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify():
    m=load(ROOT/'configs/experiment_manifest_scenarios_r1.json')
    for key in ('files_sha256','algorithm_protected_sha256','protected_sha256'):
        for p,h in m[key].items():assert sha(ROOT/p)==h,(key,p)
    frozen=load(OUT/'freeze_receipt.json')
    assert sha(ROOT/'configs/experiment_manifest_scenarios_r1.json')==frozen['manifest_sha256']
    assert sha(OUT/'frozen_source.zip')==frozen['source_zip_sha256']
    with zipfile.ZipFile(OUT/'frozen_source.zip') as z:
        for p,h in m['files_sha256'].items():assert hashlib.sha256(z.read(p)).hexdigest()==h
    results=load(OUT/'results.json');assert len(results)==18 and len({(r['scenario'],r['method']) for r in results})==18
    assert [(r['scenario'],r['method']) for r in results]==[(r['scenario'],r['method']) for r in m['cells']]
    receipt=load(OUT/'matrix_receipt.json');assert receipt['status']=='COMPLETE' and receipt['elapsed_seconds']<7200
    count=0;gap=0;all_cleanup=True;neutral_complete=0
    for row in results:
        assert row['status']=='ALL_COMPLETE' and row['completed']==row['total']==80 and row['censored']==0 and row['v2_raw_audit']=='PASS'
        d=ROOT/row['output'];s=load(d/'start.json');term=load(d/'termination.json');proc=load(d/'process.json');a=load(d/'v2_audit.json');summary=load(d/'summary.json')
        assert s['version']==m['version'] and s['method']==row['method'] and s['scenario_id']==row['scenario']
        assert proc['exit_code']==0 and not proc['external_timeout'] and proc['cleanup']['active_after_cleanup']==0
        assert term['status']=='ALL_COMPLETE' and term['completed']==80 and a['status']=='PASS' and summary['v2_raw_audit']=='PASS'
        for seal in ('output_hashes.json','audit_hashes.json'):
            for p,h in load(d/seal).items():assert sha(d/p)==h,(seal,p)
        per=list(csv.DictReader((d/'per_job.csv').open(encoding='utf8')));assert len(per)==80 and all(x['completion'] and x['jct'] for x in per)
        for x in per:assert abs(float(x['jct'])-sum(float(x[k]) for k in ('waiting','training','recovery')))<1e-6
        # Rebuild every certificate directly against original round allocation/usage.
        certs=load(d/'analysis_r1/slack_certificates.json');byround={}
        for c in certs:byround.setdefault(c['round'],[]).append(c)
        response=Responses(ROOT/row['responses']);nodes={n['id']:n for n in load(ROOT/row['cluster'])}
        with gzip.open(d/'events.jsonl.gz','rt',encoding='utf8') as f:
            for line in f:
                r=json.loads(line)
                for c in byround.get(r['round'],[]):
                    a=r['allocations'][c['job']];n=nodes[a['node']];u=r['node_usage'][a['node']]
                    for field in ('node','gpus','cpu','ram'):assert a[field]==c[field]
                    assert abs(a['rho']-c['rho'])<=1e-9
                    assert abs(n['cpu']-u[1]-c['free_cpu'])<1e-6 and abs(n['ram']-u[2]-c['free_ram'])<1e-6
                    assert u[1]-a['cpu']+c['proposed_cpu']<=n['cpu']+1e-7 and u[2]-a['ram']+c['proposed_ram']<=n['ram']+1e-7
                    rho=response.rho(c['application'],a['gpus'],a['cpu'],c['proposed_ram'])
                    assert abs(rho-c['rho_ram_only'])<1e-7
                    if c['ram_candidate_gap']:
                        assert c['job'] not in r['locks'] and rho>a['rho']+1e-7
                        assert not any(x<=c['proposed_ram']+1e-7 and response.rho(c['application'],a['gpus'],a['cpu'],x)>a['rho']+1e-7 for x in c['ram_pool'])
                        gap+=1
                    count+=1
    control=load(OUT/'cn_cm_siap_control.json');assert control['status']=='PASS' and control['jobs']==80
    for p,h in load(OUT/'post_analysis_integrity.json')['files_sha256'].items():assert sha(ROOT/p)==h
    branches={b:subprocess.check_output(['git','rev-parse',b],text=True).strip() for b in ('main','capra/v2-20261122')}
    assert branches=={'main':'1f1f07fd2238b395e108f91dbbc224d07c0c8139','capra/v2-20261122':'0b87934ae558960921889b01d14502155fb0c41c'}
    result=dict(status='PASS',utc=datetime.now(timezone.utc).isoformat(),formal_cells=18,complete_jobs=1440,all_cells_raw_audit='PASS',cn_cm_control='PASS',
        frozen_files=len(m['files_sha256']),algorithm_protected_files=len(m['algorithm_protected_sha256']),history_protected_files=len(m['protected_sha256']),
        original_branches=branches,all_owned_process_trees_empty=True,independent_slack_certificates_checked=count,independent_ram_gap_certificates_checked=gap,
        experimental_monotonic_seconds=receipt['elapsed_seconds'],no_formal_retries=True,no_algorithm_changes=True,no_remote_push=True)
    (OUT/'final_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':verify()
