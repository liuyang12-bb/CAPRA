"""Seal reproducible post-processing and delivery evidence; never run experiments."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,time
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'runs/scenarios_r1/CAPRA_V2_SCENARIOS_R1'
def load(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def main():
    assert load(OUT/'final_verification.json')['status']=='PASS'
    receipt=load(OUT/'matrix_receipt.json');assert receipt['status']=='COMPLETE'
    now=time.time();created=ROOT.stat().st_ctime
    clock=dict(working_copy_created_utc=datetime.fromtimestamp(created,timezone.utc).isoformat(),delivery_sealed_utc=datetime.fromtimestamp(now,timezone.utc).isoformat(),
        working_copy_creation_to_delivery_seconds=now-created,experimental_monotonic_seconds=receipt['elapsed_seconds'],
        scope='Worktree creation to evidence sealing includes development, validation, matrix and post-run analysis/report. Earlier prompt-reading time not included. Experiment deadline covers preparation-test start through matrix end continuously.')
    dump(OUT/'delivery_clock.json',clock)
    review=dict(status='PASS',formal_runtime_or_input_failures=0,formal_retries=0,
        postprocessing_comparator=dict(initial_log='verification.stdout.log',location='CM/Fixed round120 deepspeech2-34 rho',
            raw=1.25002,independent_interpolation=1.2500200000000001,difference=2.220446049250313e-16,
            correction='Offline certificate rho comparison uses original 1e-9 tolerance instead of exact equality; no runtime/input/algorithm change',passed_log='verification_02.stdout.log'),
        figure_review=dict(status='PASS',viewed=['figures/mean_jct.png','figures/time_decomposition.png'],
            correction='Initial time-decomposition top-row titles clipped with outside legend/constrained_layout; explicit margins fixed; original chart/report retained in report_revisions'),
        remaining_issue='Confirmed dynamic intermediate-RAM candidate omissions, deliberately unchanged in this frozen algorithm')
    dump(OUT/'postprocessing_review.json',review)
    index=['# 场景R1证据索引','',
        '- results.csv/json：18格完整状态及主指标；comparisons.csv/json：同场景三组比较，正改善表示更快。',
        '- original_v2_reference.csv、original_v2_opportunity_reference.json：原六格单列参考。',
        '- cn_cm_siap_control.json：严格逐作业/语义控制；sia_control_precheck.json为提前核查记录。',
        '- opportunity_summary.json：按实际训练时间加权的响应、相对比例、条件增益、敏感度/应用份额及机会漏斗。',
        '- paired_jobs.csv：480个同场景作业的三方法配对，保留全部正负差异。',
        '- highlighted_ram_certificates.json：动态RAM漏点示例，完整证书在各格analysis_r1/slack_certificates.json。',
        '- frozen_source.zip、freeze_receipt.json、configs/experiment_manifest_scenarios_r1.json：运行源码、输入与冻结证明。',
        '- final_verification.json：冻结、历史、原始容量/时间审计状态、独立证书及进程树清理核对。',
        '- post_analysis_integrity.json：离线分析未改变原始核心证据；postprocessing_review.json保留离线复核与图表修正说明。',
        '- delivery_clock.json、../budget_ledger.json：端到端交付口径与连续实验预算。',
        '- figures/：最终PNG/PDF；report_revisions/：初始时间图和初始报告。',
        '- ../development/：27测试、原六格复制审计、两个20作业60轮pilot、相对路径重放、孙进程清理和静态证书。',
        '', '## 固定顺序的18格','', '|序号|场景|方法|核心证据目录|','|---:|---|---|---|']
    for i,r in enumerate(load(OUT/'results.json'),1):index.append(f"|{i}|{r['scenario']}|{r['method']}|{r['scenario']}/{r['method']}/|")
    index+=['','每格包含：start.json（实际输入路径与哈希）、events.jsonl.gz（原始逐轮决策/执行）、termination.json、process.json（所属进程树清理）、per_job.csv、node_resources.csv、summary.json、v2_audit.json、output_hashes.json、audit_hashes.json，以及analysis_r1/中的独立机会统计、资源占用与证书。相邻*.stdout.log保留求解和进度输出。',
        '', '## 复核命令','', '在工作副本根目录执行：','', '```powershell',
        '.\\.venv\\Scripts\\python.exe -X utf8 -B scripts/build_scenarios_r1.py --check',
        '.\\.venv\\Scripts\\python.exe -X utf8 -B scripts/verify_scenarios_r1.py',
        '```','', '分析和报告命令见docs/SCENARIOS_R1_RESULTS.md。分析工具属于正式运行后增加的只读工具，未修改冻结运行源码。证据哈希清单evidence_hashes.json覆盖本轮结果、报告及后处理工具（排除该清单自身和最终核对的可刷新日志）。']
    (OUT/'EVIDENCE_INDEX.md').write_text('\n'.join(index)+'\n',encoding='utf8')
    report=ROOT/'docs/SCENARIOS_R1_RESULTS.md'
    text=report.read_text(encoding='utf8')
    marker='\n## 最终交付核对\n'
    if marker in text:text=text.split(marker)[0]
    text+=marker+f"\n最终核对PASS；1035个冻结文件、1002个算法/上游文件、1209个历史文件保持一致。复核1222条独立闲置资源证书，其中288条为RAM候选漏点证书（证书数不是独立轮次数，不能累计共享收益）。原main/v2分支提交不变，18格所属进程树全部清空。\n\n工作副本创建到本次封存{(now-created)/60:.2f}分钟；连续实验时钟78.61分钟，端到端口径及UTC起止见delivery_clock.json。\n\n正式运行没有失败或重试。事后证书终检曾用exact equality比较两种插值，差异仅2.22e-16；改用既有1e-9容差后通过，保留verification.stdout.log和verification_02.stdout.log。初始时间分解图首行标题被布局挤掉，修正边距后重新查看两张PNG通过，原图/初报告保留report_revisions。以上仅后处理修改，未改变冻结算法、输入或正式运行。\n\n本轮到此结束，无自动算法修复、追加矩阵或远端推送。\n"
    report.write_text(text,encoding='utf8')
    files=[p for p in (ROOT/'runs/scenarios_r1').rglob('*') if p.is_file() and p.name not in ('evidence_hashes.json',)]
    files+=list((ROOT/'data/scenarios_r1').glob('*'))
    files+=[ROOT/p for p in ('SCENARIOS_R1_README.md','configs/scenarios_r1.json','configs/experiment_manifest_scenarios_r1.json','docs/SCENARIOS_R1_DESIGN.md','docs/SCENARIOS_R1_RESULTS.md','docs/SCENARIOS_R1_EXECUTION_ORDER.txt')]
    files+=list((ROOT/'scripts').glob('*scenarios_r1.py'))+[ROOT/'scripts/scenario_control.py']
    hashes={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(files))}
    dump(OUT/'evidence_hashes.json',dict(status='PASS',files_sha256=hashes,clock=clock))
    for p,h in hashes.items():assert sha(ROOT/p)==h
    print(json.dumps(dict(status='SEALED',files=len(hashes),working_copy_to_delivery_minutes=(now-created)/60,experiment_minutes=receipt['elapsed_seconds']/60)))
if __name__=='__main__':main()
