"""Final R2 evidence inventory and delivery clock; no experiment or historical mutation."""
from datetime import datetime,timezone
from r2_utils import *
def main():
    verified=load(RUN/'final_verification.json');matrix=load(RUN/'matrix_receipt.json');budget=ledger()
    assert verified['status'] in ('COMPLETE_PASS','PARTIAL_WITH_EXPLICIT_GAPS')
    assert (ROOT/'docs/CAPRA_R2_CODE.patch').exists() and (ROOT/'docs/CAPRA_R2_INTERPRETATION.md').exists()
    assert (ROOT/'docs/NEXT_VALIDATION_PLAN.md').exists() and (RUN/'analysis/recommendation.json').exists()
    now=time.time();created=ROOT.stat().st_ctime;began=datetime.fromisoformat(budget['start_utc']).timestamp();ended=(RUN/'matrix_receipt.json').stat().st_mtime
    clock=dict(worktree_created_utc=datetime.fromtimestamp(created,timezone.utc).isoformat(),budget_started_utc=budget['start_utc'],matrix_finished_utc=datetime.fromtimestamp(ended,timezone.utc).isoformat(),sealed_utc=datetime.fromtimestamp(now,timezone.utc).isoformat(),
        initial_development_seconds=began-created,shared_experiment_seconds=matrix['elapsed_seconds'],post_matrix_analysis_report_seconds=now-ended,total_worktree_to_delivery_seconds=now-created,
        scope='End-to-end starts at worktree creation, excludes earlier prompt reading. Shared monotonic budget includes every preparation/validation failure and gap through final matrix cleanup. Post-matrix analysis/report separate.')
    dump(RUN/'delivery_clock.json',clock)
    summary=load(RUN/'analysis/recommendation.json')
    readme=['# CAPRA R2 本地交付入口','',f"基准 `{BASE}`；分支 `capra/ablation-ram-r2`。旧main/v2/R1和原目录保持原字节。本轮未推送。",'',
        f"状态：{verified['status']}，正式完成{verified['formal_complete']}/9，新增完成{verified['new_complete_jobs']}/720。建议：{summary['recommended']}；仅提出选择建议，没有在结果后删除R或追加实验。",'',
        '- [最终中文报告](docs/CAPRA_R2_RESULTS.md)',
        '- [研究判断](docs/CAPRA_R2_INTERPRETATION.md)',
        '- [冻结设计](docs/CAPRA_R2_DESIGN.md)',
        '- [完整代码diff](docs/CAPRA_R2_CODE.patch)',
        '- [后续验证计划，未执行](docs/NEXT_VALIDATION_PLAN.md)',
        '- [新增九格结果](runs/ablation_ram_r2/results.csv)',
        '- [含复用来源的分析结果](runs/ablation_ram_r2/analysis/results.csv)',
        '- [全部比较与逐任务结果](runs/ablation_ram_r2/analysis/)',
        '- [证据索引](runs/ablation_ram_r2/EVIDENCE_INDEX.md)',
        '- [最终核对](runs/ablation_ram_r2/final_verification.json)',
        '- [源码快照](runs/ablation_ram_r2/source_snapshot.zip)',
        '', f"共享实验时钟{matrix['elapsed_seconds']/60:.2f}/90分钟；工作副本创建到封存{(now-created)/60:.2f}分钟。所有模拟调用见simulation_calls.json，全部所属树清理和失败记录保留。",'',
        '用户手动推送命令：','', '```powershell','git -C "D:\\科研启航\\CAPRA-ablation-ram-r2" push -u origin capra/ablation-ram-r2','```']
    (ROOT/'R2_README.md').write_text('\n'.join(readme)+'\n',encoding='utf8')
    report=ROOT/'docs/CAPRA_R2_RESULTS.md';text=report.read_text(encoding='utf8');marker='\n## 最终封存\n'
    if marker in text:text=text.split(marker)[0]
    text+=marker+f"\n最终核对：{verified['status']}。A/B共{verified['formal_complete']}/9格、新增{verified['new_complete_jobs']}/720次作业完整；旧R1历史1440次与本轮只读复用720次均不包装为新增样本。\n\n初步开发（工作副本创建到预算起点）{clock['initial_development_seconds']/60:.2f}分钟；连续测试/验证/实验预算{clock['shared_experiment_seconds']/60:.2f}/90分钟；矩阵后纯离线分析/报告{clock['post_matrix_analysis_report_seconds']/60:.2f}分钟；端到端（工作副本创建至封存）{clock['total_worktree_to_delivery_seconds']/60:.2f}分钟，不包含此前阅读任务说明。UTC与时间来源见delivery_clock.json。\n\n保护1713个基准文件，原R1工作副本及main/v2/R1分支未改变。所有正式/冒烟所属进程树清理已核对。版本及源码哈希见freeze_receipt和两份manifest，完整代码diff为docs/CAPRA_R2_CODE.patch，证据hash为evidence_hashes.json。\n\n本轮未推送。手动推送：`git -C \"D:/科研启航/CAPRA-ablation-ram-r2\" push -u origin capra/ablation-ram-r2`。最终本地提交SHA在交付消息中给出，避免把包含自身提交SHA的报告做成循环身份。\n"
    report.write_text(text,encoding='utf8')
    index=['# R2证据索引','',
        '- root results.csv/json：仅新增9格完整状态、删失及错误；matrix_index.json为精确顺序和元数据。',
        '- CAPRA_V2_ABLATION_R2/：A新增6格；CAPRA_V2_RAM_R2/：B新增3格，各有events/start/termination/process/per_job/node_resources/summary/r2_audit及hash。',
        '- analysis/stage_A.csv：三个场景五方法，旧9格复用+新增6格；stage_B.csv：CM三方法各自修复前后，未重跑比例背景。',
        '- analysis/source_index.csv/json：每来源的提交/快照、版本、路径和原始文件哈希；analysis/raw_integrity.json证明分析未写原始核心文件。',
        '- analysis/comparisons.csv/json、paired_jobs.csv、worst_cases.json：全部预定正负比较、比值P95/max、快平慢及最坏任务，非独占slowdown。',
        '- analysis/metrics.json和cells/：各格每应用、条件增益、F/K/R、计时、RAM实际训练配额和终局连续剩余机会。',
        '- analysis/recommendation.json及docs/CAPRA_R2_INTERPRETATION.md：最终FK/FKR建议及限制，不触发新算法/实验。',
        '- development/unit_tests_receipt、unit_simulation_calls_*.json：33测试和内部18次Job.step；tests_*.log保留原日志。',
        '- development/state_replay_selection/results：54个固定旧状态，缺失首次类别明确为空。',
        '- development/ram_certificate_group_replays及receipt：全部288旧证书按151完整节点分组，非独立最大配额累加。',
        '- development/smoke_01/02：至多12作业30轮，两次短验证，未完成整体JCT为空。',
        '- source_snapshot.zip、freeze_receipt及configs的A/B manifests：同时冻结，zip不含manifest避免自引用。',
        '- budget_ledger.json、simulation_calls.json、delivery_clock.json：一次性5400秒预算、全部模拟调用和端到端阶段计时。',
        '- development/preparation_01/02.stdout.log：准备期Git继承配置缺项失败，未运行测试/模拟，保留原日志，同一截止继续。',
        '- final_verification.json：历史、源码、版本、输入/输出、审计、清理及完整/缺口状态。',
        '- figures/：至少三张PNG/PDF，分别对应A五方法、CM修复前后账本、R收益和开销；报告修订如有保留report_revisions。',
        '- docs/NEXT_VALIDATION_PLAN.md及analysis/next_candidate_inputs.json：Saturn7/8只读计数和哈希；未生成新工作负载或执行。','',
        '## 新增正式格','', '|序号|阶段|场景|方法|状态|完成|目录|','|---:|---|---|---|---|---:|---|']
    for r in load(RUN/'results.json'):index.append(f"|{r['index']}|{r['phase']}|{r['scenario']}|{r['method']}|{r['status']}|{r.get('completed')}|{r['output']}|")
    (RUN/'EVIDENCE_INDEX.md').write_text('\n'.join(index)+'\n',encoding='utf8')
    protected=load(DEV/'protected_base.json');files=[p for p in RUN.rglob('*') if p.is_file() and p.name!='evidence_hashes.json']
    for folder in ('src','scripts','tests','configs','docs'):
        files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.relative_to(ROOT).as_posix() not in protected)
    files.append(ROOT/'R2_README.md');hashes={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(files))}
    dump(RUN/'evidence_hashes.json',dict(status='SEALED',files_sha256=hashes,scope='All R2 results, new source/analysis/tests, docs, manifests; excludes this hash index itself; historical bytes protected separately'))
    for p,h in hashes.items():assert sha(ROOT/p)==h
    print(__import__('json').dumps(dict(status=verified['status'],sealed_files=len(hashes),shared_experiment_minutes=clock['shared_experiment_seconds']/60,end_to_end_minutes=clock['total_worktree_to_delivery_seconds']/60)))
if __name__=='__main__':main()
