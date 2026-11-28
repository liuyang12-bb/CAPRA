"""Only the fixed eight formal cells, with persistent absolute/cumulative limits."""
from pathlib import Path
import argparse,sys,os,time,json,shutil,traceback,csv
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from capra.protocol_direct_eval_r6 import *
from budget_direct_eval_r6 import Budget

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',default='configs/experiment_manifest_direct_eval_r6.json');p.add_argument('--resume',action='store_true');args=p.parse_args()
    budget=Budget(resume=args.resume);py=[sys.executable,'-X','utf8','-B'];manifest=ROOT/args.manifest
    def phase(kind,script,cap,group_cap=None):
        prior=[] if budget.data is None else [a for a in budget.data['attempts'] if a['kind']==kind]
        if prior and prior[-1]['state']=='PASS':return prior[-1]
        left=cap if group_cap is None or budget.data is None else group_cap-sum(a.get('charged_seconds',0) for a in budget.data['attempts'] if a['kind'] in ('environment','tests'))
        if left<31:return dict(state='NOT_STARTED_BUDGET')
        case=RUN/'development'/kind/f'attempt{len(prior)+1:02d}'
        if kind=='tests':os.environ['R6_VALIDATION_ARTIFACTS']=str(case/'artifacts')
        return budget.run(kind,py+[script],case,min(cap,left))
    if not manifest.exists():
        environment=phase('environment','scripts/environment_direct_eval_r6.py',120,300)
        if environment['state']!='PASS':return 1
        tests=phase('tests','scripts/tests_direct_eval_r6.py',180,300)
        if tests['state']!='PASS':return 1
        commit=phase('code_commit','scripts/commit_direct_eval_r6.py',60)
        if commit['state']!='PASS':return 1
        freeze=phase('freeze','scripts/freeze_direct_eval_r6.py',90)
        if freeze['state']!='PASS':return 1
    else:
        assert args.resume,'REFUSE_IMPLICIT_RESUME';budget.start()
    m=load(manifest);assert m['algorithm_base_commit']==BASE and m['version']==VERSION
    ledger_path=RUN/'matrix_ledger.json'
    if ledger_path.exists():matrix=load(ledger_path)
    else:
        matrix=dict(version=VERSION,algorithm_base_commit=BASE,cells=[dict(c,output=None,attempts=[],execution_status='NOT_STARTED',audit_status='PENDING',formal_performance_experiment='NOT_STARTED',reason='CREATED',submitted_count=0,completed_count=0) for c in m['cells']]);dump(ledger_path,matrix)
    prior_history=[a for a in budget.data['attempts'] if a['kind']=='history_qualification']
    if not prior_history:
        if budget.remaining()>=150:budget.run('history_qualification',py+['scripts/reuse_direct_eval_r6.py'],RUN/'development/history_qualification/attempt01',120)
    for scenario in dict.fromkeys(c['scenario'] for c in m['cells']):
        for method in ('SIA-SMART-P','CAPRA-FK','CAPRA'):
            q=RUN/'historical_reuse'/scenario/method/'reuse_eligibility.json'
            if not q.exists():dump(q,dict(scenario=scenario,method=method,state='UNVERIFIED',reason='History qualification did not finish in its fixed <=120s budget',result_origin='REUSED_R4'))
    blocked=False
    for c in matrix['cells']:
        if c['execution_status']=='COMPLETE' and c['audit_status']=='PASS':
            assert args.resume
            for name,h in c['sealed_files_sha256'].items():assert sha(ROOT/c['output']/name)==h,('RESUME_SEAL_CHANGED',c['index'],name)
            continue
        if c['attempts']:
            # Explicit package-fix retries need a new reviewed manifest/source revision.
            # Never retry automatically for poor performance, partial completion or timeout.
            blocked=blocked or c.get('reason')=='CORRECTNESS_FAILURE'
            continue
        if blocked:
            c.update(reason='NOT_STARTED_CORRECTNESS_BLOCK');dump(ledger_path,matrix);continue
        if budget.remaining()<780 or (ROOT/'STOP_REQUEST.json').exists():
            c.update(reason='NOT_STARTED_BUDGET' if budget.remaining()<780 else 'USER_STOP');dump(ledger_path,matrix);continue
        attempt=1;raw=ROOT/next(x['output'] for x in m['cells'] if x['index']==c['index'])/f'attempt{attempt:02d}';control=RUN/'control'/f'formal_{c["index"]:02d}'/f'attempt{attempt:02d}'
        assert not raw.exists();c.update(output=raw.relative_to(ROOT).as_posix(),execution_status='RUNNING',audit_status='PENDING',formal_performance_experiment='RUNNING',reason=None);dump(ledger_path,matrix)
        cmd=py+['-m','capra.runner_direct_eval_r6','--manifest',args.manifest,'--cell',str(c['index']),'--output',str(raw),'--wall-limit','540','--global-deadline-epoch',str(budget.data['deadline_epoch']-210),'--global-deadline-monotonic',str(budget.data['deadline_monotonic']-210)]
        process=budget.run('formal',cmd,control,600,570,cell=c['index']);c['attempts'].append(dict(attempt=attempt,control=control.relative_to(ROOT).as_posix(),raw=raw.relative_to(ROOT).as_posix(),process=process))
        raw.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(control/'process.json',raw/'process.json');shutil.copyfile(control/'stdout.log',raw/'stdout.log')
        if (raw/'summary.json').exists():
            s=load(raw/'summary.json');good=process['state']=='PASS' and s['execution_status']=='COMPLETE' and s['audit_status']=='PASS' and s['completed_count']==s['submitted_count']==s['arrived_count']==80
            c.update(execution_status='COMPLETE' if good else ('PARTIAL' if process['state'] in ('PASS','EXTERNAL_TIMEOUT') else 'FAILED'),audit_status=s['audit_status'] if process['state']=='PASS' else 'PENDING',formal_performance_experiment='COMPLETE' if good else ('PARTIAL' if process['state'] in ('PASS','EXTERNAL_TIMEOUT') else 'FAILED'),reason=s['termination_reason'] if process['state']=='PASS' else process['state'],submitted_count=s['submitted_count'],arrived_count=s['arrived_count'],completed_count=s['completed_count'])
        else:
            term=load(raw/'termination.json') if (raw/'termination.json').exists() else {}
            s=dict(version=VERSION,phase='FORMAL',method=c['method'],scenario=c['scenario'],execution_status='FAILED',audit_status='FAIL',formal_performance_experiment='FAILED',expected_job_count=80,jobs_loaded_count=80,submitted_count=term.get('submitted_count',0),arrived_count=term.get('arrived_count',0),completed_count=term.get('completed',0),censored_count=80-term.get('completed',0),reason=process['state'])
            for k in ('mean_jct','median_jct','p95_jct','p99_jct','makespan','total_waiting','total_training','total_recovery'):s[k]=None
            dump(raw/'summary.json',s);dump(raw/'independent_audit.json',dict(status='FAIL',reason='No successful independently audited summary; inspect failure/audit_failure/stdout'))
            if not (raw/'per_job.csv').exists():
                with (raw/'per_job.csv').open('w',encoding='utf8',newline='') as f:
                    fields=['job','application','arrival','completion','jct','waiting','training','recovery','progress','audit_status'];writer=csv.DictWriter(f,fields);writer.writeheader();writer.writerows(dict(job=r['name'],application=r['application'],arrival=r['time'],audit_status='UNVERIFIED') for r in input_rows(ROOT/c['workload']))
            if not (raw/'node_resources.csv').exists():(raw/'node_resources.csv').write_text('round,time,node,gpus,cpu,ram\n',encoding='utf8')
            c.update(execution_status='FAILED',audit_status='FAIL',formal_performance_experiment='FAILED',reason=process['state'],submitted_count=s['submitted_count'],completed_count=s['completed_count'])
        if (raw/'failure.json').exists() or (raw/'audit_failure.json').exists():c['reason']='CORRECTNESS_FAILURE';blocked=True
        closure={p.name:sha(p) for p in raw.iterdir() if p.is_file() and p.name!='attempt_closure.json'};dump(raw/'attempt_closure.json',dict(files_sha256=closure,execution_status=c['execution_status'],audit_status=c['audit_status'],source_manifest_sha256=sha(manifest)))
        c['sealed_files_sha256']={p.name:sha(p) for p in raw.iterdir() if p.is_file()};c['performance_metrics']={k:s.get(k) if c['execution_status']=='COMPLETE' and c['audit_status']=='PASS' else None for k in ('mean_jct','median_jct','p95_jct','p99_jct','makespan')}
        dump(ledger_path,matrix)
        print(json.dumps(dict(event='FORMAL_CELL_END',index=c['index'],scenario=c['scenario'],method=c['method'],execution_status=c['execution_status'],audit_status=c['audit_status'],completed=c.get('completed_count',0),mean_jct=c['performance_metrics']['mean_jct'],remaining_seconds=budget.remaining())),flush=True)
    if budget.remaining()>=61:
        history= [a for a in budget.data['attempts'] if a['kind']=='report'];case=RUN/'development/report'/f'attempt{len(history)+1:02d}'
        budget.run('report',py+['scripts/report_direct_eval_r6.py','--manifest',args.manifest,'--budgeted'],case,min(180,budget.remaining()))
    if budget.remaining()>=61:
        history=[a for a in budget.data['attempts'] if a['kind']=='final_verify'];case=RUN/'development/final_verify'/f'attempt{len(history)+1:02d}'
        budget.run('final_verify',py+['scripts/verify_direct_eval_r6.py','--manifest',args.manifest,'--budgeted'],case,min(180,budget.remaining()))
    budget.save();complete=sum(c['execution_status']=='COMPLETE' and c['audit_status']=='PASS' for c in matrix['cells'])
    dump(RUN/'batch_completion.json',dict(status='COMPLETE_FORMAL_MATRIX' if complete==8 else 'PARTIAL_FORMAL_DELIVERY',complete_cells=complete,expected_cells=8,completed_job_executions=sum(c.get('completed_count',0) for c in matrix['cells']),blocked_correctness=blocked,elapsed_window_seconds=time.monotonic()-budget.data['start_monotonic'],remaining_seconds=budget.remaining(),all_owned_cleanup_zero=all(a.get('cleanup',{}).get('active_after_cleanup',0)==0 for a in budget.data['attempts'])))
    print('R6_BATCH_FINISHED',complete,'/8; remaining',budget.remaining(),flush=True)
    return 0
if __name__=='__main__':raise SystemExit(main())
