# R2证据索引

- root results.csv/json：仅新增9格完整状态、删失及错误；matrix_index.json为精确顺序和元数据。
- CAPRA_V2_ABLATION_R2/：A新增6格；CAPRA_V2_RAM_R2/：B新增3格，各有events/start/termination/process/per_job/node_resources/summary/r2_audit及hash。
- analysis/stage_A.csv：三个场景五方法，旧9格复用+新增6格；stage_B.csv：CM三方法各自修复前后，未重跑比例背景。
- analysis/source_index.csv/json：每来源的提交/快照、版本、路径和原始文件哈希；analysis/raw_integrity.json证明分析未写原始核心文件。
- analysis/comparisons.csv/json、paired_jobs.csv、worst_cases.json：全部预定正负比较、比值P95/max、快平慢及最坏任务，非独占slowdown。
- analysis/metrics.json和cells/：各格每应用、条件增益、F/K/R、计时、RAM实际训练配额和终局连续剩余机会。
- analysis/recommendation.json及docs/CAPRA_R2_INTERPRETATION.md：最终FK/FKR建议及限制，不触发新算法/实验。
- development/unit_tests_receipt、unit_simulation_calls_*.json：33测试和内部18次Job.step；tests_*.log保留原日志。
- development/state_replay_selection/results：54个固定旧状态，缺失首次类别明确为空。
- development/ram_certificate_group_replays及receipt：全部288旧证书按151完整节点分组，非独立最大配额累加。
- development/smoke_01/02：至多12作业30轮，两次短验证，未完成整体JCT为空。
- source_snapshot.zip、freeze_receipt及configs的A/B manifests：同时冻结，zip不含manifest避免自引用。
- budget_ledger.json、simulation_calls.json、delivery_clock.json：一次性5400秒预算、全部模拟调用和端到端阶段计时。
- development/preparation_01/02.stdout.log：准备期Git继承配置缺项失败，未运行测试/模拟，保留原日志，同一截止继续。
- final_verification.json：历史、源码、版本、输入/输出、审计、清理及完整/缺口状态。
- figures/：至少三张PNG/PDF，分别对应A五方法、CM修复前后账本、R收益和开销；报告修订如有保留report_revisions。
- docs/NEXT_VALIDATION_PLAN.md及analysis/next_candidate_inputs.json：Saturn7/8只读计数和哈希；未生成新工作负载或执行。

## 新增正式格

|序号|阶段|场景|方法|状态|完成|目录|
|---:|---|---|---|---|---:|---|
|1|A|w2_dense_original|SIA-P-K|ALL_COMPLETE|80|runs/ablation_ram_r2/CAPRA_V2_ABLATION_R2/w2_dense_original/SIA-P-K|
|2|A|w2_dense_original|CAPRA-FK|ALL_COMPLETE|80|runs/ablation_ram_r2/CAPRA_V2_ABLATION_R2/w2_dense_original/CAPRA-FK|
|3|A|w6_dense_original|SIA-P-K|ALL_COMPLETE|80|runs/ablation_ram_r2/CAPRA_V2_ABLATION_R2/w6_dense_original/SIA-P-K|
|4|A|w6_dense_original|CAPRA-FK|ALL_COMPLETE|80|runs/ablation_ram_r2/CAPRA_V2_ABLATION_R2/w6_dense_original/CAPRA-FK|
|5|A|w2_dense_cm|SIA-P-K|ALL_COMPLETE|80|runs/ablation_ram_r2/CAPRA_V2_ABLATION_R2/w2_dense_cm/SIA-P-K|
|6|A|w2_dense_cm|CAPRA-FK|ALL_COMPLETE|80|runs/ablation_ram_r2/CAPRA_V2_ABLATION_R2/w2_dense_cm/CAPRA-FK|
|7|B|w2_dense_cm|CAPRA-Fixed|ALL_COMPLETE|80|runs/ablation_ram_r2/CAPRA_V2_RAM_R2/w2_dense_cm/CAPRA-Fixed|
|8|B|w2_dense_cm|CAPRA-FK|ALL_COMPLETE|80|runs/ablation_ram_r2/CAPRA_V2_RAM_R2/w2_dense_cm/CAPRA-FK|
|9|B|w2_dense_cm|CAPRA|ALL_COMPLETE|80|runs/ablation_ram_r2/CAPRA_V2_RAM_R2/w2_dense_cm/CAPRA|
