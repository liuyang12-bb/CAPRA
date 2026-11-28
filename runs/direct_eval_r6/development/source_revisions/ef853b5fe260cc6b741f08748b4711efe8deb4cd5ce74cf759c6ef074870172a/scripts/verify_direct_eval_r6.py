"""Portable read-only evidence replay. Never import production decisions or Job."""
from pathlib import Path,PureWindowsPath
import argparse,sys,time,zipfile,hashlib,csv,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from capra.protocol_direct_eval_r6 import RUN,BASE,R4,VERSION,INPUTS,load,dump,sha,digest,git
from capra.audit_direct_eval_r6 import audit_records

def recorded_imports_owned(start):
    info=start['import_audit'];original=info['ROOT'];cls=PureWindowsPath if PureWindowsPath(original).drive else Path;root=cls(original)
    assert cls(info['prefix'])==root/'.venv'
    for p in info['module_files'].values():
        path=cls(p)
        if getattr(path,'drive','').lower()==getattr(root,'drive','').lower() and getattr(root,'drive',''):assert path.is_relative_to(root),('ORIGINAL_FOREIGN_IMPORT',p)

def verify_manifest(m):
    assert m['version']==VERSION and m['phase']=='FORMAL' and m['algorithm_base_commit']==BASE and m['inherited_direct_parent']==R4
    head=git('rev-parse','HEAD').decode().strip()
    assert git('merge-base','--is-ancestor',BASE,m['actual_execution_head'],check=False).returncode==0
    assert git('merge-base','--is-ancestor',m['actual_execution_head'],head,check=False).returncode==0
    assert sha(ROOT/m['source_snapshot'])==m['source_snapshot_sha256']
    with zipfile.ZipFile(ROOT/m['source_snapshot']) as z:
        for p,h in m['source_files_sha256'].items():assert hashlib.sha256(z.read(p)).hexdigest()==h,('ARCHIVE_BYTES',p)
    for p,h in m['execution_source_files_sha256'].items():assert sha(ROOT/p)==h,('FROZEN_EXECUTION_BYTES',p)
    for p,h in load(RUN/'protected_base_sha256.json').items():assert sha(ROOT/p)==h,('OLD_BYTES_CHANGED',p)
    for p,h in INPUTS.items():assert sha(ROOT/p)==h
    tooling=[]
    for p,h in m['source_files_sha256'].items():
        if p not in m['execution_source_files_sha256'] and sha(ROOT/p)!=h:tooling.append(dict(path=p,frozen=h,current=sha(ROOT/p)))
    if tooling:
        ledger=load(RUN/'tooling_revision_ledger.json')
        for change in tooling:
            current=change['frozen']
            for row in ledger:
                if row['path']==change['path'] and row['before_sha256']==current:assert row['reason'];current=row['after_sha256']
            assert current==change['current'],('UNEXPLAINED_TOOLING_CHANGE',change)
    return dict(current_head=head,execution_head=m['actual_execution_head'],protected_files=len(load(RUN/'protected_base_sha256.json')),frozen_execution_files=len(m['execution_source_files_sha256']),tooling_revisions=tooling)

def compare_jobs(actual,logged):
    source={r['job']:r for r in logged};assert set(source)=={r['job'] for r in actual}
    for row in actual:
        old=source[row['job']]
        for field in ('arrival','completion','waiting','training','recovery','progress','jct'):
            if row[field] is None:assert old[field] in ('',None)
            else:assert abs(row[field]-float(old[field]))<=1e-7,(row['job'],field,row[field],old[field])

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',default='configs/experiment_manifest_direct_eval_r6.json');p.add_argument('--output');p.add_argument('--budgeted',action='store_true');args=p.parse_args()
    if args.budgeted:
        from budget_direct_eval_r6 import assert_window
        assert_window()
    path=Path(args.manifest);path=path if path.is_absolute() else ROOT/path;m=load(path);began=time.monotonic();meta=verify_manifest(m)
    output=Path(args.output) if args.output else RUN/'verification'/f'check_{time.time_ns()}'
    assert not output.exists();output.mkdir(parents=True);matrix=load(RUN/'matrix_ledger.json')['cells'];new=[]
    for cell in matrix:
        result=dict(index=cell['index'],scenario=cell['scenario'],method=cell['method'],execution_status=cell['execution_status'],audit_status=cell['audit_status'])
        if cell['execution_status']=='COMPLETE' and cell['audit_status']=='PASS':
            d=ROOT/cell['output'];start=load(d/'start.json');recorded_imports_owned(start)
            assert start['frozen_code_head']==m['actual_execution_head'] and start['source_fingerprint']==m['source_fingerprint'] and start['manifest_sha256']==sha(path)
            assert git('merge-base','--is-ancestor',start['actual_execution_head'],meta['current_head'],check=False).returncode==0
            for name,h in load(d/'evidence_hashes.json').items():assert sha(d/name)==h,('SEALED_CELL',cell['index'],name)
            closure=load(d/'attempt_closure.json')
            for name,h in closure['files_sha256'].items():assert sha(d/name)==h
            process=load(d/'process.json');assert process['state']=='PASS' and process['cleanup']['active_after_cleanup']==0
            summary,jobs,nodes,checks=audit_records(d);stored=load(d/'summary.json')
            assert summary['execution_status']=='COMPLETE' and summary['audit_status']=='PASS' and summary['completed_count']==80
            for name in ('mean_jct','median_jct','p95_jct','p99_jct','makespan','total_waiting','total_training','total_recovery'):assert abs(summary[name]-stored[name])<=1e-7
            assert summary['selection_nonempty_rounds']==stored['selection_nonempty_rounds'] and summary['counts']==stored['counts']
            compare_jobs(jobs,list(csv.DictReader((d/'per_job.csv').open(encoding='utf8',newline=''))))
            dump(output/f'new_{cell["index"]:02d}.json',dict(status='PASS',checks=checks,mean_jct=summary['mean_jct']));result['replay']='PASS'
        else:
            result['replay']='NOT_VALID_FOR_PERFORMANCE_COMPARISON'
            if cell.get('output') and (ROOT/cell['output']/'summary.json').exists():
                stored=load(ROOT/cell['output']/'summary.json');assert all(stored.get(k) is None for k in ('mean_jct','median_jct','p95_jct','p99_jct','makespan'))
        new.append(result)
    historical=[]
    for scenario,_ in list(dict.fromkeys((c['scenario'],c['method']) for c in m['cells'])):
        for method in ('SIA-SMART-P','CAPRA-FK','CAPRA'):
            ident=(scenario,method)
            if ident in [(x['scenario'],x['method']) for x in historical]:continue
            qpath=RUN/'historical_reuse'/scenario/method/'reuse_eligibility.json'
            if not qpath.exists():historical.append(dict(scenario=scenario,method=method,state='UNVERIFIED'));continue
            q=load(qpath);entry=dict(scenario=scenario,method=method,state=q['state'])
            if q['state']=='ELIGIBLE':
                d=ROOT/q['source_directory']
                for name,h in q['source_files_sha256'].items():assert sha(d/name)==h
                summary,jobs,nodes,checks=audit_records(d,historical=True);assert summary['execution_status']=='COMPLETE' and summary['completed_count']==80
                stored=load(RUN/'historical_reuse'/scenario/method/'recomputed_summary.json')
                for name in ('mean_jct','median_jct','p95_jct','p99_jct','makespan'):assert abs(summary[name]-stored[name])<=1e-7
                entry['replay']='PASS'
            historical.append(entry)
    b=load(RUN/'budget_ledger.json')
    for attempt in b['attempts']:
        if attempt.get('cleanup'):assert attempt['cleanup']['active_after_cleanup']==0
    complete=sum(c['execution_status']=='COMPLETE' and c['audit_status']=='PASS' for c in matrix)
    result=dict(verification_status='PASS',delivery_status='COMPLETE' if complete==8 else 'PARTIAL',valid_new_cells=complete,expected_new_cells=8,new_cells=new,historical_cells=historical,source=meta,wall_seconds=time.monotonic()-began,no_scheduler_or_training_calls=True,no_sealed_source_writes=True)
    dump(output/'verification.json',result);dump(RUN/'latest_verification_receipt.json',dict(output=output.relative_to(ROOT).as_posix(),sha256=sha(output/'verification.json'),status=result['verification_status'],valid_new_cells=complete))
    print(json.dumps(dict(status='R6_VERIFY_PASS',valid_new_cells=complete,eligible_R4=sum(x['state']=='ELIGIBLE' for x in historical),wall_seconds=result['wall_seconds'])),flush=True)
if __name__=='__main__':main()
