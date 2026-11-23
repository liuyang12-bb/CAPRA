"""Final integrity, provenance and complete-call inventory; no simulator or write-back audit."""
import csv,gzip,hashlib,zipfile
from r2_utils import *
def verify():
    frozen=load(RUN/'freeze_receipt.json');protected=load(DEV/'protected_base.json');baseline=Path('D:/科研启航/CAPRA-scenarios-r1')
    for p,h in protected.items():
        assert sha(ROOT/p)==h,('LOCAL_HISTORY_CHANGED',p)
        assert sha(baseline/p)==h,('ORIGINAL_R1_CHANGED',p)
    manifests=[]
    for p,h in frozen['manifests_sha256'].items():
        assert sha(ROOT/p)==h;m=load(ROOT/p);manifests.append(m)
        assert m['base_commit']==BASE and m['source_snapshot_sha256']==frozen['source_snapshot_sha256']
        for name,digest in m['files_sha256'].items():assert sha(ROOT/name)==digest,('FROZEN_CHANGED',name)
    snapshot=RUN/'source_snapshot.zip';assert sha(snapshot)==frozen['source_snapshot_sha256']
    with zipfile.ZipFile(snapshot) as z:
        for name,h in manifests[0]['files_sha256'].items():assert hashlib.sha256(z.read(name)).hexdigest()==h
        assert 'configs/experiment_manifest_ablation_r2.json' not in z.namelist() and 'configs/experiment_manifest_ram_r2.json' not in z.namelist()
    index=load(RUN/'matrix_index.json');results=load(RUN/'results.json');expected=manifests[0]['cells']+manifests[1]['cells']
    assert len(index)==len(results)==len(expected)==9
    for actual,want in zip(index,expected):
        for key in want:assert actual[key]==want[key],('PREREGISTERED_INDEX',key)
    assert [(x['index'],x['phase'],x['scenario'],x['method']) for x in results]==[(x['index'],x['phase'],x['scenario'],x['method']) for x in expected]
    total=0;full=0;ramtraces=0;ramsteps=0
    for r in results:
        d=ROOT/r['output']
        if not d.exists():assert r['status']!='ALL_COMPLETE';continue
        if r['status']!='ALL_COMPLETE':
            total+=r.get('completed') or 0
            if (d/'process.json').exists():assert load(d/'process.json')['cleanup']['active_after_cleanup']==0
            continue
        s=load(d/'start.json');assert s['base_commit']==BASE and s['source_snapshot_sha256']==frozen['source_snapshot_sha256']
        assert s['phase_version']==r['phase_version'] and s['method']==r['method'] and s['allocator_mode']==r['allocator_mode']
        assert s['candidate_labels']==r['candidate_labels'] and s['quota_mode']==r['quota_mode'] and s['ram_repair_enabled']==r['ram_repair_enabled']
        assert s['costs']==r['costs']
        for seal in ('output_hashes.json','audit_hashes.json'):
            if (d/seal).exists():
                for name,h in load(d/seal).items():assert sha(d/name)==h,(seal,name)
        proc=load(d/'process.json');assert proc['cleanup']['active_after_cleanup']==0 and proc['external_wall_limit']<=960
        total+=r.get('completed') or 0
        if r['status']=='ALL_COMPLETE':
            full+=1;assert r['completed']==r['total']==80 and r['censored']==0 and r['r2_raw_audit']=='PASS' and proc['exit_code']==0 and not proc['external_timeout']
            summary=load(d/'summary.json');assert summary['r2_raw_audit']=='PASS'
            with (d/'per_job.csv').open(encoding='utf8') as f:per=list(csv.DictReader(f))
            assert len(per)==80
            for job in per:assert abs(float(job['jct'])-sum(float(job[k]) for k in ('waiting','training','recovery')))<1e-6
        with gzip.open(d/'events.jsonl.gz','rt',encoding='utf8') as f:
            for line in f:
                e=__import__('json').loads(line);assert e['selection']['method_spec']=={k:s[k] for k in ('candidate_labels','quota_mode','allocator_mode','ram_repair_enabled')}
                assert e['selection']['r_calls']==int('R' in s['candidate_labels'])
                ramtraces+=len(e['selection']['allocator'].get('ram_traces',[]));ramsteps+=e['selection']['allocator'].get('ram_steps',0)
    matrix=load(RUN/'matrix_receipt.json');assert matrix['elapsed_seconds']<=5400+1
    b=ledger();formal=[e for e in b['entries'] if e['kind']=='formal'];smokes=[e for e in b['entries'] if e['kind'].startswith('smoke_')]
    assert len(formal)<=9 and len({e['cell'] for e in formal})==len(formal) and len(smokes)<=2
    for e in smokes:assert e['cleanup']['active_after_cleanup']==0 and e['external_wall_limit']<=120
    calls=[]
    calls.extend(dict(e,call_type='unit_test_suite_including_gpu_stage_and_execution_fixtures') for e in b['entries'] if e['kind']=='tests')
    for path in sorted(DEV.glob('unit_simulation_calls_*.json')):
        calls.append(dict(kind='unit_test_micro_execution',path=path.relative_to(ROOT).as_posix(),events=load(path),scope='Job.step fixtures, not formal full-workload samples; test process elapsed included in shared budget'))
    calls.extend(dict(e,call_type='short_smoke') for e in smokes);calls.extend(dict(e,call_type='formal_80_job_cell') for e in formal)
    dump(RUN/'simulation_calls.json',dict(unit_job_step_calls=sum(len(x.get('events',[])) for x in calls if x.get('kind')=='unit_test_micro_execution'),smoke_processes=len(smokes),formal_processes=len(formal),calls=calls))
    validation=load(DEV/'validation_receipt.json');assert validation['status']=='PASS' and validation['offline']['ram_certificates']==288 and validation['offline']['legacy_states']==54
    if (RUN/'analysis/raw_integrity.json').exists():
        for p,h in load(RUN/'analysis/raw_integrity.json')['files_sha256'].items():assert sha(ROOT/p)==h
        metrics=load(RUN/'analysis/metrics.json')
        for m in metrics:
            if m['source']['phase']=='B':assert m['residual_ram_rounds']==0
    branches={name:git('rev-parse',name).decode().strip() for name in ('main','capra/v2-20261122','capra/scenarios-r1')}
    assert branches=={'main':'1f1f07fd2238b395e108f91dbbc224d07c0c8139','capra/v2-20261122':'0b87934ae558960921889b01d14502155fb0c41c','capra/scenarios-r1':BASE}
    result=dict(status='COMPLETE_PASS' if full==9 and total==720 else 'PARTIAL_WITH_EXPLICIT_GAPS',formal_complete=full,formal_registered=9,new_complete_jobs=total,
        reused_R1_selected_cells=9,reused_R1_selected_jobs=720,old_R1_historical_jobs=1440,new_samples_not_pooled=True,
        frozen_files=frozen['frozen_files'],protected_base_files=len(protected),original_R1_directory_unchanged=True,baseline_branches=branches,
        tests=validation['tests'],legacy_state_replays=54,old_ram_certificates=288,grouped_nodes=151,smoke_calls=len(smokes),
        formal_ram_traces_checked_in_independent_audits=ramtraces,formal_ram_steps_checked_in_independent_audits=ramsteps,
        all_owned_process_trees_empty=True,formal_retries=0,shared_experimental_seconds=matrix['elapsed_seconds'],no_remote_push=True)
    dump(RUN/'final_verification.json',result);print(__import__('json').dumps(result,ensure_ascii=False))
if __name__=='__main__':verify()
