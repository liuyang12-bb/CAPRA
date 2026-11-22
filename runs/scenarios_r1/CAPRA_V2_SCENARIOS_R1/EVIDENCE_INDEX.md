# 场景R1证据索引

- results.csv/json：18格完整状态及主指标；comparisons.csv/json：同场景三组比较，正改善表示更快。
- original_v2_reference.csv、original_v2_opportunity_reference.json：原六格单列参考。
- cn_cm_siap_control.json：严格逐作业/语义控制；sia_control_precheck.json为提前核查记录。
- opportunity_summary.json：按实际训练时间加权的响应、相对比例、条件增益、敏感度/应用份额及机会漏斗。
- paired_jobs.csv：480个同场景作业的三方法配对，保留全部正负差异。
- highlighted_ram_certificates.json：动态RAM漏点示例，完整证书在各格analysis_r1/slack_certificates.json。
- frozen_source.zip、freeze_receipt.json、configs/experiment_manifest_scenarios_r1.json：运行源码、输入与冻结证明。
- final_verification.json：冻结、历史、原始容量/时间审计状态、独立证书及进程树清理核对。
- post_analysis_integrity.json：离线分析未改变原始核心证据；postprocessing_review.json保留离线复核与图表修正说明。
- delivery_clock.json、../budget_ledger.json：端到端交付口径与连续实验预算。
- figures/：最终PNG/PDF；report_revisions/：初始时间图和初始报告。
- ../development/：27测试、原六格复制审计、两个20作业60轮pilot、相对路径重放、孙进程清理和静态证书。

## 固定顺序的18格

|序号|场景|方法|核心证据目录|
|---:|---|---|---|
|1|w2_dense_original|SIA-P|w2_dense_original/SIA-P/|
|2|w2_dense_original|CAPRA-Fixed|w2_dense_original/CAPRA-Fixed/|
|3|w2_dense_original|CAPRA|w2_dense_original/CAPRA/|
|4|w6_dense_original|SIA-P|w6_dense_original/SIA-P/|
|5|w6_dense_original|CAPRA-Fixed|w6_dense_original/CAPRA-Fixed/|
|6|w6_dense_original|CAPRA|w6_dense_original/CAPRA/|
|7|w2_dense_cpu2|SIA-P|w2_dense_cpu2/SIA-P/|
|8|w2_dense_cpu2|CAPRA-Fixed|w2_dense_cpu2/CAPRA-Fixed/|
|9|w2_dense_cpu2|CAPRA|w2_dense_cpu2/CAPRA/|
|10|w2_dense_cpu6|SIA-P|w2_dense_cpu6/SIA-P/|
|11|w2_dense_cpu6|CAPRA-Fixed|w2_dense_cpu6/CAPRA-Fixed/|
|12|w2_dense_cpu6|CAPRA|w2_dense_cpu6/CAPRA/|
|13|w2_dense_cn|SIA-P|w2_dense_cn/SIA-P/|
|14|w2_dense_cn|CAPRA-Fixed|w2_dense_cn/CAPRA-Fixed/|
|15|w2_dense_cn|CAPRA|w2_dense_cn/CAPRA/|
|16|w2_dense_cm|SIA-P|w2_dense_cm/SIA-P/|
|17|w2_dense_cm|CAPRA-Fixed|w2_dense_cm/CAPRA-Fixed/|
|18|w2_dense_cm|CAPRA|w2_dense_cm/CAPRA/|

每格包含：start.json（实际输入路径与哈希）、events.jsonl.gz（原始逐轮决策/执行）、termination.json、process.json（所属进程树清理）、per_job.csv、node_resources.csv、summary.json、v2_audit.json、output_hashes.json、audit_hashes.json，以及analysis_r1/中的独立机会统计、资源占用与证书。相邻*.stdout.log保留求解和进度输出。

## 复核命令

在工作副本根目录执行：

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts/build_scenarios_r1.py --check
.\.venv\Scripts\python.exe -X utf8 -B scripts/verify_scenarios_r1.py
```

分析和报告命令见docs/SCENARIOS_R1_RESULTS.md。分析工具属于正式运行后增加的只读工具，未修改冻结运行源码。证据哈希清单evidence_hashes.json覆盖本轮结果、报告及后处理工具（排除该清单自身和最终核对的可刷新日志）。
