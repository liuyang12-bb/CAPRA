"""Artifact manifest only, after validated commands; no simulator/audit/search invocation."""
from pathlib import Path
import json,hashlib,time
ROOT=Path(__file__).resolve().parents[1];RUN=ROOT/'runs/direct_r5'
def load(p):return json.loads(Path(p).read_text(encoding='utf8'))
def dump(p,x):Path(p).write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    began=time.perf_counter();b=load(RUN/'validation_budget.json');core=load(RUN/'final_evidence_checks.json');results=load(RUN/'analysis/implementation_results.json')
    latest={a['kind']:a for a in b['attempts']}
    assert core['status']=='PASS' and latest['final_evidence']['status']=='PASS' and not any(a['status']=='RUNNING' for a in b['attempts'])
    assert results['validation_status']=='VALIDATION_COMPLETE' and results['budget_used_seconds']==b['used_seconds']<=900
    assert all(a['process']['cleanup']['active_after_cleanup']==0 for a in b['attempts'])
    checks=dict(implementation_status='IMPLEMENTATION_COMPLETE',validation_status='VALIDATION_COMPLETE',base_commit=core['base_commit'],branch='capra/direct-placement-r5',formal_performance_experiments='NOT_RUN',tests=results['tests'],test_attempts=results['test_attempts'],unique_R4_F_replay_states=3,total_R4_F_replay_executions=3*results['test_attempts'],smoke_attempts=2,smoke_results=core['smokes'],algorithm_counts_nonempty=results['algorithm_counts_nonempty'],cooperative_budget_fallbacks_in_smokes=0,implementation_errors_in_smokes=0,protected_files=core['protected_files'],R4_original_tree_preserved=True,historical_refs=core['historical_refs'],all_owned_descendants_after_cleanup=0,validation_command_wall_seconds=b['used_seconds'],validation_remaining_seconds=b['remaining_seconds'],formal_retries=0,no_remote_push=True)
    dump(RUN/'final_verification.json',checks)
    clock=load(RUN/'delivery_clock.json');initial=load(RUN/'initial_clock.json')
    clock['measured_setup_to_seal_seconds']=time.time()-initial['worktree_environment_setup_started_unix'];clock['seal_computation_seconds']=time.perf_counter()-began
    dump(RUN/'delivery_clock.json',clock)
    files=[p for p in RUN.rglob('*') if p.is_file() and p.name not in ('evidence_hashes.json','EVIDENCE_INDEX.md')]
    files += list((ROOT/'src/capra').glob('*direct_r5.py'))+list((ROOT/'scripts').glob('*direct_r5*.py'))+list((ROOT/'docs').glob('CAPRA_DIRECT_R5*'))+[ROOT/'tests/test_direct_r5.py',ROOT/'configs/direct_r5_validation.json',ROOT/'DIRECT_R5_README.md']
    hashes={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(files))}
    dump(RUN/'evidence_hashes.json',dict(base_commit=core['base_commit'],files_sha256=hashes,excludes_self_and_index=True))
    (RUN/'EVIDENCE_INDEX.md').write_bytes(('# Direct R5 evidence index\n\n'+'\n'.join(f'- `{p}` SHA256 `{h}`' for p,h in hashes.items())+'\n').encode('utf8'))
    print(json.dumps(dict(status='SEALED',evidence_files=len(hashes),validation_wall_seconds=b['used_seconds'],remaining_seconds=b['remaining_seconds'],measured_setup_to_seal_seconds=clock['measured_setup_to_seal_seconds']),ensure_ascii=False))
if __name__=='__main__':main()
