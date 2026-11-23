# CAPRA R2：预先冻结的机制消融与RAM补充分配

唯一基准 `81b1109ab1124feeac4e846003f4383b39143fc4`；独立分支 `capra/ablation-ram-r2`，工作副本 `D:/科研启航/CAPRA-ablation-ram-r2`。任务原文 `CAPRA_R2_EXECUTION_ORDER.txt`。历史说明中的旧矩阵/不修改算法边界针对R1；本次按用户明确的6+3授权执行，不运行旧入口，不修改历史，不自动推送。

## 固定方法和代码边界

|方法|候选|配额|
|---|---|---|
|SIA-P|P|实际比例|
|CAPRA-Fixed|F|辅助优化|
|SIA-P-K|F,K|实际比例|
|CAPRA-FK|F,K|辅助优化|
|CAPRA|F,K,R|辅助优化|

新增 `placement_r2.py` 继承原布局构造，注入显式配额策略。SIA-P-K的F/K调用独立比例策略，保留锁，未锁CPU/RAM精确等于节点容量×GPU份额；不调用旧NodeAllocator的solve/layout/pairs/optimize，不调用RAM修复。两个FK方法在选择循环中精确只构造F/K，不计算R后丢弃。F/K/R规则、GPU-DP、身份稳定、Phi、EPS=1e-9、delay/changes/候选顺序平局保持原样。

所有基准跟踪文件均保护原字节，包括旧placement、node_allocator、runner/audit、GPU/execution/identity/costs/response/上游、输入及全部历史。R2使用独立runner_r2、audit_r2和audit_ram_r2；公共审计仅写新的R2输出。新增包装器不更改旧NodeAllocator的初始向量选择、回收、有限升级及断言。

## RAM补充 ram_slack_v1

先取得旧NodeAllocator最终选定的完整节点解，再运行一次末尾补充。GPU、CPU、节点及任务集合固定，锁原样保留。每次对每个未锁任务取大于当前RAM且不超过真实余量上界的原轴点×GPU，加当前真实m_max；8位坐标去重时保留较小真实值，绝不向上舍入借用容量容差。上界使用math.fsum计算其他任务占用，必要时nextafter朝下移动至物理可行；RAM增量和rho增量均须严格大于1e-9。

候选顺序为 `(-round(Delta_rho/(Delta_ram/node.ram),12), -round(Delta_rho,12), job_id, RAM)`。每次只接受第一项，立即更新完整节点及余量，直到无正增益。步数界为进入补充时每个未锁任务尚未跨过的原RAM轴点数之和+1；越界报错，不截断。增加RAM不改原初始向量优胜者。RAM平坦/饱和/无余量/全锁定严格无操作。

缓存仅在单次决策内，修复缓存key带mode、节点和任务集合；返回缓存中的修复后解。R的部分布局试算与F/K最终配额共用同一包装器。legacy路径直接原NodeAllocator；none路径只做比例保留。旧upgrades/upgrade_bound不混入RAM步骤。记录独立ram_steps/ram_step_bound/ram_candidates/ram_repair_seconds、所有节点试算的初始/终态/逐步候选和更新。

## 验证清单（首次执行前固定）

1. 运行原27项及新增6项测试；逐次登记原测试内部Job.step（微型执行fixture也计入预算）。新增覆盖已知416.68点、三任务证书、平坦/饱和/锁/无余量、多个M共享余量、浮点边界、确定性/有限性/缓存、两FK方法在K可行及失败时的R调用隔离、比例路径四个优化入口调用隔离。
2. 三场景各旧SIA-P/Fixed/CAPRA：前2/后2非空轮，首次K/R选中、首次恢复锁、首次K不可行，去重。不存在类别明确记空。重建不可变阶段输入，只重放调度，不调用GPU仿真/Job.step；比候选/布局/配额/评分/可行性/选择/平局，排除计时缓存；同状态检查FK的F/K等于旧完整CAPRA。规则不随结果改变。
3. 原CM Fixed/CAPRA全部288条RAM-gap证书核对原始单任务可行性；按源方法/轮/节点分组，从完整实际节点配额顺序修复并由独立审计重放。不要求多个目标同时取得各自独立最大配额，不累计假想JCT收益。保留更新及终局剩余机会。
4. 至多两次短冒烟：A/SIA-P-K/W2原画像、B/CAPRA-FK/CM，各最多12作业30轮、runner90秒、所属进程120秒。单独目录，未完成全体JCT为空。
5. 恢复相同锁定环境和数值线程；版本/依赖锁/HiGHS封装二进制哈希记录。真实Windows Job Object孙进程清理验证沿用R1机制，R2再核对本环境实例。

## 严格9格及冻结

A=`CAPRA_V2_ABLATION_R2`，先运行：W2原画像SIA-P-K、FK；W6原画像SIA-P-K、FK；CM SIA-P-K、FK。SIA-P-K用none/proportional，FK用legacy。
B=`CAPRA_V2_RAM_R2`，再运行CM Fixed、FK、CAPRA，均ram_slack_v1。正式第一格前同时冻结两阶段清单、完全相同源码包及RAM规则。旧18格只读复用，均标基准SHA/run version/路径/哈希，不算新增执行。

输入直接使用R1现有W2/W6 dense CSV、CPU3集群、original/CM响应表，核对原SHA，不重新生成。80作业、原到达、40GPU/6节点、每型两节点、4/8GPU、单节点任务、batch/训练量、原恢复费用、interval60、H180、seed0与数值线程1不变。neutral始终false。控制器wall不扣模拟JCT，真实恢复计入；aux-only仍零恢复费。

start与索引记录base/source_snapshot/manifest/phase/method、精确候选集与配额模式、实际输入路径/哈希、环境、费用和限制。源码zip不包含阶段manifest；manifest指zip SHA；start指manifest SHA，避免自引用。

## 独立审计与计时

audit_r2使用独立literal方法规范，保留旧原始GPU/batch、恢复锁、身份稳定、费用、Phi、平局、进度rho一次、时间与JCT检查。新增比例精确性、R调用数0、完整RAM初始/终态和每步候选/来源/余量/增益/排序/界/最终合法机会重放，不导入Placement/NodeAllocator/repair作为验算器。trace_rho按既有数值容差核对后，用已核对数值独立计算舍入优先级；避免不同等价插值路径末位差异制造伪错误。

完整decision_seconds保持原端到端边界；各候选真实构造/评估时间、R调用和跳过、RAM调用/更新/候选/步骤/耗时另记。RAM、mapping/scoring已嵌套在候选耗时内，不重复相加。旧细分计时缺失标不可得，不补跑。主开销只用非空轮，另列all_rounds；median/P95/max及>5秒次数比例同时报告。

## 统一预算及失败规则

初步实现完成后，首次测试/状态验证前建立5400秒连续单调时钟截止。测试、离线回放、两次冒烟、必要修正重验、冻结、9格、核验写盘清理都计入，A/B不重置。阅读初步开发和矩阵后纯离线报告另记。每格runner900秒、所属树960秒、6000轮，取全局剩余约束并预留至少30秒；保留30轮无进展、连续三次非空决策>30秒、STOP_REQUEST。串行执行，不按进程名清理其他任务，不预登记正式重试。正式错误停止后续格并保留NOT_RUN，不修改冻结代码混合结果。预算不足交付真实缺口。

## 分析与研究判断

固定对照：比例位置保留、辅助优化的位置保留、对齐稳定后资源增量、R动态增量；B再比较每方法自身修复前后和同修复版本Fixed/FK/FKR。改善率正为更快；等待/训练/恢复差称时间账本而非严格因果。逐作业比值叫相对基线JCT比值，非经典独占slowdown。完整保留均值、分位尾部、单作业最坏退化及开销。

实际训练段统计rho、rho/rho_prop、CPU/RAM条件差和正增益训练份额；条件差不相加解释总收益。RAM新点、额外配额及实际使用训练份额，按真实执行而非只看试算统计。终局连续单任务RAM机会单独检查，不能用旧pool_ram判断修复后的漏点。依据实测建议FK或FKR，但不自动删除R或追加实验。只准备Saturn7/8候选来源和下一轮计划，不运行新负载。
