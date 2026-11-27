"""Final hash/provenance census only. No simulation, optimization or state search."""
import zipfile,json,time,hashlib
from r4_utils import *
def main():
    began=time.perf_counter();protected=load(DEV/'protected_base.json');historical=load(RUN/'history_worktrees_verification.json')
    assert historical['status']=='PASS' and len(historical['worktrees'])==4
    for p,h in protected.items():
        assert sha(ROOT/p)==h,('BASE_CHANGED_IN_R4',p)
        assert sha(Path('D:/科研启航/CAPRA-smart-holdout-r3')/p)==h,('R3_ORIGINAL_TREE_CHANGED',p)
    source=load(RUN/'freeze_receipt.json') if (RUN/'freeze_receipt.json').exists() else None
    if source:
        mp=ROOT/source['manifest'];assert sha(mp)==source['manifest_sha256'];m=load(mp);assert m['base_commit']==BASE and len(m['cells'])==12 and not m['equivalence_reuse']
        archive=ROOT/m['source_snapshot'];assert sha(archive)==m['source_snapshot_sha256']==source['source_snapshot_sha256']
        for p,h in m['files_sha256'].items():assert sha(ROOT/p)==h,('FROZEN_SOURCE_CHANGED',p)
        with zipfile.ZipFile(archive) as z:
            assert source['manifest'] not in z.namelist()
            for p,h in m['files_sha256'].items():assert hashlib.sha256(z.read(p)).hexdigest()==h
    cells=load(RUN/'results.json') if (RUN/'results.json').exists() else [];index=load(RUN/'matrix_index.json') if source else [];states=load(RUN/'matrix_ledger.json')['cells'] if source else [];calls=load(RUN/'simulation_calls.json');budget=ledger();cleanups=[]
    for e in budget['entries']:
        if 'cleanup' in e:cleanups.append(dict(kind=e['kind'],cleanup=e['cleanup']))
        if e.get('process'):cleanups.append(dict(kind='formal',cell=e['cell'],cleanup=e['process']['cleanup']))
    assert all(x['cleanup']['active_after_cleanup']==0 for x in cleanups)
    physical_calls=[e for e in budget['entries'] if e['kind']=='formal'];assert len(physical_calls)<=12 and len({x['cell'] for x in physical_calls})==len(physical_calls),'FORMAL_RETRY'
    assert calls['formal_executed']==len(physical_calls) and calls['smoke_executed']<=2
    complete=[x for x in cells if x['state']=='COMPLETE_PASS']
    assert len(cells)==len({x['index'] for x in cells})
    for c in complete:
        d=ROOT/c['output'];s=load(d/'start.json');sm=load(d/'summary.json');au=load(d/'r4_audit.json');pr=load(d/'process.json');st=next(x for x in states if x['index']==c['index'])
        assert st['state']=='COMPLETE_PASS' and s['base_commit']==BASE and sm['r4_raw_audit']=='PASS' and au['status']=='PASS' and sm['completed']==sm['total']==80
        assert s['source_snapshot_sha256']==source['source_snapshot_sha256'] and s['manifest_sha256']==source['manifest_sha256']
        assert pr['exit_code']==0 and pr['cleanup']['active_after_cleanup']==0 and not pr['external_timeout']
        for p,h in load(d/'output_hashes.json').items():assert sha(d/p)==h
        for p,h in load(d/'audit_hashes.json').items():assert sha(d/p)==h
        for p,h in st['final_files_sha256'].items():assert sha(d/p)==h,('LEDGER_CLOSED_FILE_CHANGED',p)
        reg=next(x for x in m['cells'] if x['index']==c['index']);assert reg['scenario']==c['scenario'] and reg['method']==c['method'] and reg['input_hashes']==c['input_hashes']
    for name in ('raw_integrity.json','diagnostic_raw_integrity.json'):
        p=RUN/'analysis'/name
        if p.exists():
            for rel,h in load(p)['files_sha256'].items():assert sha(ROOT/rel)==h
    diagnosis=load(RUN/'analysis/diagnosis_receipt.json') if (RUN/'analysis/diagnosis_receipt.json').exists() else None
    if diagnosis:
        assert diagnosis['small_states']<=8 and diagnosis['enumerated_layouts']<=128 and diagnosis['Job_step_calls']==0 and diagnosis['GPU_MIP_calls']==0
        # The diagnosis itself completed in an owned child before budget_end.
        assert any(x['kind']=='bounded_opportunity_diagnosis' and x['status']=='PASS' for x in budget['entries'])
    end=next(x for x in reversed(budget['entries']) if x['kind']=='budget_end');elapsed=end['elapsed_seconds'];initial=load(DEV/'initial_clock.json');start_epoch=datetime.fromisoformat(budget['start_utc']).timestamp();now=time.time();created=initial['worktree_created_unix']
    dump(RUN/'delivery_clock.json',dict(initial_reading_implementation_since_worktree_seconds=start_epoch-created,initial_reading_before_worktree_seconds=None,unified_budget_seconds=10800,unified_budget_elapsed_seconds=elapsed,post_budget_pure_offline_analysis_report_seconds=now-start_epoch-elapsed,worktree_to_seal_seconds=now-created,scope='Measured from independent worktree creation; preceding initial attachment reading not instrumented',final_hash_check_seconds=time.perf_counter()-began))
    verification=dict(status='COMPLETE_PASS' if len(complete)==12 and diagnosis and diagnosis['status']=='PASS' else 'PARTIAL_DELIVERY',base_commit=BASE,branch='capra/pressure-opportunity-r4',protected_files=len(protected),R3_original_tree_preserved=True,historical_worktrees=[{k:x[k] for k in ('worktree','commit','status','tracked_files')} for x in historical['worktrees']],formal_physical_executed=len(physical_calls),formal_complete=len(complete),new_complete_job_executions=80*len(complete),formal_retries=0,equivalence_reused_physical_cells=0,test_suite_attempts=len(calls['test_calls']),unit_Job_step_calls=sum(len(x) for x in calls['test_calls']),smoke_calls=calls['smoke_executed'],all_owned_descendants_after_cleanup=0,cleanup_receipts=cleanups,budget_elapsed_seconds=elapsed,budget_within_limit=elapsed<=10800,diagnosis=diagnosis,final_check_simulator_calls=0,final_check_state_search_calls=0,no_remote_push=True)
    dump(RUN/'final_verification.json',verification)
    lines=['# CAPRA R4 本地交付入口','',f'状态：{verification["status"]}。基准 `{BASE}`；独立分支 `capra/pressure-opportunity-r4`。实际完整{len(complete)}/12格，新增完整{len(complete)*80}/960作业，全部格要求实际运行，无等价复用。R3算法及历史字节保留；本轮未推送。','', '- [中文主报告](docs/CAPRA_R4_RESULTS.md)','- [预注册设计](docs/CAPRA_R4_DESIGN.md)','- [下一阶段决定](docs/CAPRA_R4_NEXT_PLAN.md)','- [准确代码补丁](docs/CAPRA_R4_CODE.patch)','- [输入生成与逐行来源](data/pressure_r4/)','- [实际物理结果](runs/pressure_r4/results.csv)','- [含历史参照的结果与来源](runs/pressure_r4/analysis/)','- [严格机会漏斗](runs/pressure_r4/analysis/opportunity_funnel.csv)','- [代表作业与动态轨迹](runs/pressure_r4/analysis/opportunity_cases.json)','- [有限小状态审查](runs/pressure_r4/analysis/bounded_layout_reviews.json)','- [图件PNG/PDF](runs/pressure_r4/figures/)','- [源码快照](runs/pressure_r4/source_snapshot.zip)','- [最终核验](runs/pressure_r4/final_verification.json)','- [时间账本](runs/pressure_r4/delivery_clock.json)','- [证据哈希](runs/pressure_r4/evidence_hashes.json)','', '手动推送：','','```powershell','git -C "D:/科研启航/CAPRA-pressure-opportunity-r4" push -u origin capra/pressure-opportunity-r4','```','']
    (ROOT/'R4_README.md').write_bytes('\n'.join(lines).encode('utf8'))
    files=[p for p in RUN.rglob('*') if p.is_file() and p.name not in ('evidence_hashes.json','EVIDENCE_INDEX.md')]
    files += [p for p in (ROOT/'docs').glob('*R4*') if p.is_file()]+list((ROOT/'src/capra').glob('*r4.py'))+list((ROOT/'scripts').glob('*r4.py'))+[ROOT/'tests/test_r4.py',ROOT/'R4_README.md']
    files += [p for p in (ROOT/'data/pressure_r4').rglob('*') if p.is_file() and '__pycache__' not in p.parts]+list((ROOT/'configs').glob('*_r4.json'))
    hashes={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(files))};dump(RUN/'evidence_hashes.json',dict(base_commit=BASE,files_sha256=hashes,excludes_self_and_index=True))
    (RUN/'EVIDENCE_INDEX.md').write_bytes(('## R4 evidence index\n\n'+'\n'.join(f'- `{p}` SHA256 `{h}`' for p,h in hashes.items())+'\n').encode('utf8'))
    print(json.dumps({k:v for k,v in verification.items() if k!='cleanup_receipts'},ensure_ascii=False))
if __name__=='__main__':main()
