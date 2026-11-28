"""Budgeted R4 qualification: exact sources/inputs/environment and pure raw re-audit."""
from pathlib import Path
import sys,time,csv,zipfile,traceback
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from capra.protocol_direct_eval_r6 import *
from capra.audit_direct_eval_r6 import audit_records,write_table
def main():
    began=time.monotonic();m=load(ROOT/'configs/experiment_manifest_direct_eval_r6.json');old=load(ROOT/'configs/experiment_manifest_pressure_r4.json');out=RUN/'historical_reuse';out.mkdir(exist_ok=True)
    global_error=None
    try:
        assert old['version']=='CAPRA_V2_PRESSURE_R4' and old['base_commit']=='5af0bdb6b86b797225908f717b5b9324cd48a539'
        assert sha(ROOT/old['source_snapshot'])==old['source_snapshot_sha256']
        assert old['environment']['highs_wrapper_sha256']==m['environment']['highs_wrapper_sha256']
        assert old['environment']['dependency_lock_sha256']==m['environment']['dependency_lock_sha256']
        assert old['environment']['versions']==m['environment']['versions'] and old['environment']['numeric_environment']==NUMERIC
        with zipfile.ZipFile(ROOT/old['source_snapshot']) as z:
            for p,h in old['files_sha256'].items():
                assert sha(ROOT/p)==h,('R4_SOURCE_INPUT_BYTES_CHANGED',p)
                assert __import__('hashlib').sha256(z.read(p)).hexdigest()==h
        assert git('merge-base','--is-ancestor',R4,BASE,check=False).returncode==0
    except Exception as e:global_error=repr(e)
    results=[]
    scenarios=list(dict.fromkeys(s for s,_ in ORDER))
    for scenario in scenarios:
        for method in ('SIA-SMART-P','CAPRA-FK','CAPRA'):
            target=out/scenario/method;target.mkdir(parents=True,exist_ok=True);src=ROOT/'runs/pressure_r4/CAPRA_V2_PRESSURE_R4'/scenario/method
            result=dict(scenario=scenario,method=method,display_method='CAPRA-FKR' if method=='CAPRA' else method,result_origin='REUSED_R4',source_commit=R4,source_directory=src.relative_to(ROOT).as_posix(),state='UNVERIFIED',reason=None)
            try:
                if global_error:raise AssertionError(global_error)
                start=load(src/'start.json');summary=load(src/'summary.json');process=load(src/'process.json')
                assert summary['r4_raw_audit']=='PASS' and summary['completed']==summary['total']==80 and summary['status']=='ALL_COMPLETE'
                assert process['exit_code']==0 and not process['external_timeout'] and process['cleanup']['active_after_cleanup']==0
                assert summary['scheduling_wall_charged_to_simulation'] is False
                expected=next(c for c in m['cells'] if c['scenario']==scenario)
                for kind,key in (('workload','workload'),('cluster','cluster'),('responses','responses')):
                    assert start['inputs'][kind]['relative']==expected[key] and start['inputs'][kind]['sha256']==INPUTS[expected[key]]
                assert start['source_snapshot_sha256']==old['source_snapshot_sha256']
                for seal in ('output_hashes.json','audit_hashes.json'):
                    for p,h in load(src/seal).items():assert sha(src/p)==h
                derived,jobs,nodes,checks=audit_records(src,historical=True)
                assert derived['execution_status']=='COMPLETE' and derived['audit_status']=='PASS'
                for a,b in [('mean_jct','mean_jct'),('median_jct','p50_jct'),('p95_jct','p95_jct'),('p99_jct','p99_jct'),('makespan','makespan')]:assert abs(derived[a]-summary[b])<=1e-7,(a,derived[a],summary[b])
                logged={r['job']:r for r in csv.DictReader((src/'per_job.csv').open(encoding='utf8',newline=''))}
                assert set(logged)=={r['job'] for r in jobs}
                for r in jobs:
                    for field in ('arrival','completion','waiting','training','recovery','progress','jct'):assert abs(r[field]-float(logged[r['job']][field]))<=1e-7
                dump(target/'recomputed_summary.json',derived);dump(target/'independent_audit.json',checks);write_table(target/'per_job_recomputed.csv',jobs,list(jobs[0]))
                result.update(state='ELIGIBLE',reason='Exact input/order/80 jobs, frozen shared and method-specific source, performance tables, costs/solver/numeric environment, full raw resource/recovery/training/JCT replay pass; runtime guard limits did not truncate',source_version=start['version'],runtime_source_snapshot=old['source_snapshot'],runtime_source_snapshot_sha256=old['source_snapshot_sha256'],source_algorithm_base=start['base_commit'],source_environment=start['numeric_environment'],method_difference='SmartGpuStage adapted smart + proportional/none' if method=='SIA-SMART-P' else 'GpuStage + frozen '+('/'.join(start['candidate_labels']))+' and ram_slack_v1',wall_time_scope='HISTORICAL_REFERENCE_ONLY_NO_WALL_SPEEDUP_RATIO',source_files_sha256={p.name:sha(p) for p in src.iterdir() if p.is_file()})
            except Exception as e:
                result.update(state='INCOMPATIBLE',reason=repr(e),traceback=traceback.format_exc())
            dump(target/'reuse_eligibility.json',result);results.append(result)
            dump(out/'eligibility_index.json',results)
            print(json.dumps(dict(event='R4_QUALIFIED',scenario=scenario,method=method,state=result['state'])),flush=True)
    dump(out/'receipt.json',dict(status='FINISHED',eligible=sum(r['state']=='ELIGIBLE' for r in results),expected=12,wall_seconds=time.monotonic()-began,no_historical_closed_loop_execution=True,no_writes_to_R4=True))
if __name__=='__main__':main()
