# CAPRA Direct R6：冻结算法的正式对照预登记

算法固定基准 `b40cdefdff27d46d8044510652a557e8d7599920`；R4来源 `ffa953fb9cd12773992559512d85065bbd26b7b2`。
独立分支 `capra/direct-evaluation-r6`，新运行版本 `CAPRA_V2_DIRECT_EVAL_R6`，新根目录 `runs/direct_eval_r6/`。
所有R5基准旧受控文件保持原字节；只新增R6接口、审计、验证、分析、报告和证据。本轮不自动push。

## 方法与明确工程边界

- `CAPRA-Direct`：直接调用原 `runner_direct_r5.decide`，不复制/更换Direct决策，不改R5常量。
- `CAPRA-F-Only`：同一GpuStage一次，原DirectPlacement.prepare_f，原identity.reference和RepairAllocator，完整F只提交一次。
  不调用select、construct_d、can_finish、D_AFTER；候选只有F，D_status=NOT_APPLICABLE_F_ONLY。
- 相同80作业、GPU/训练性能数据、集群、画像、成本、恢复锁、batch、seed0/线程1/60秒/H180；每格独立闭环、独立新进程、严格串行。
- Direct同状态F只用于机制分析；不代替F-only完整轨迹。两策略进度分化后的GPU配置可以不同。
- 不新增K/R/S/局部交换/搜索/门控/参数优化，不改变wall time未计入模拟JCT的既有语义。
- 5秒是原协作式候选预算，不是硬上限。F-only不运行D不算预算回退。
- R5的zero-cost机制fixture把全部转换成本（包括迁移）设0；只作机制测试，不是实际恢复费用下的性能证据。

## 唯一正式矩阵

|顺序|场景|方法|
|---|---|---|
|01|saturn7_dense05_original|CAPRA-F-Only|
|02|saturn7_dense05_original|CAPRA-Direct|
|03|saturn7_dense05_cm|CAPRA-Direct|
|04|saturn7_dense05_cm|CAPRA-F-Only|
|05|saturn8_dense05_original|CAPRA-Direct|
|06|saturn8_dense05_original|CAPRA-F-Only|
|07|saturn8_dense05_cm|CAPRA-F-Only|
|08|saturn8_dense05_cm|CAPRA-Direct|

完整原80行，不截断、不修改到达、顺序或训练量；共640次提交，不是640个独立研究样本。
使用R4的两份dense05、cluster_cpu3、Original/CM，用户指定5个SHA硬校验。
40GPU/6节点/三类型每型两节点，max_jobs=None、max_rounds=6000保护上限、interval60、H180。

## 必要验证

仅验证新增接口：3个F-only小状态（新/运行/真实锁）对原prepare_f完整一致，并spy禁D路径；
Direct函数identity及一个真实Job单步与冻结R5执行循环一致；完整80行及FORMAL元数据；
训练进度增长不误停，真正停滞与连续3次>30秒决策能停止；轻量owned孙进程清理和预算不能重置。
不再跑新smoke、不重做R5全套验证/历史矩阵、不追加布局oracle。

## 共用绝对执行窗口

第一条实际验证命令启动时记录单调时钟/UTC绝对截止，共5400秒；累计实际命令wall与绝对时间同时约束。
读取/编码/独立环境准备在窗口前另记；窗口后所有验证、冻结、历史资格、8格、复算、图表、终检和清理都受限。
环境+定向验证累计<=300秒；历史资格<=120秒；未完成历史资格标UNVERIFIED不重跑历史方法。
每逻辑格所有attempt累计<=600秒，最多2次，仅明确包装正确性修复可触发第二次，不为负收益/超时/部分完成重跑。
runner内部540秒；工作进程+审计+summary至多570秒；预留30秒清理，外层总600秒。
始终为收尾预留180秒，新格剩余不足780秒则NOT_STARTED_BUDGET。
复用原scenario_control.Owned（挂入Job Object后才resume，KILL_ON_JOB_CLOSE），只清理拥有的进程树。
每项记录PID、命令、起止、退出、状态、实际wall、清理；重启不重置，未闭合RUNNING保守计费不当PASS。

## 停止与不完整语义

保留ALL_COMPLETE/USER_STOP/WALL_LIMIT/MAX_ROUNDS/GLOBAL_BUDGET/NO_PROGRESS_30_ROUNDS/
CONTROL_OVERHEAD_3X30S/IMPLEMENTATION_ERROR/AUDIT_ERROR。
只有全部到达后连续30轮没有实际训练进度增长才判无进展，不能看完成任务数。
完整决策连续3轮>30秒则停止。真实资源/费用/训练错误停止后续格，不伪装成正常F保护。
输入加载数80与实际submitted/arrived/completed分开。未完整或审计不通过，总体JCT/makespan留空。

## 冻结、实际HEAD和可移植复核

先本地提交新实现，再冻结manifest和源码快照。记录algorithm_base_commit、inherited_direct_parent、
冻结代码HEAD、每次实际运行HEAD、source fingerprint、最终交付SHA；R5模块BASE仍是历史父常量。
源码快照不含指向它的manifest，避免自哈希循环。覆盖新旧实际执行源码、关键审计、传递SIA源码、
全部实际SIA traces/训练性能表、输入5文件、依赖锁与求解器二进制hash/选项。
旧受控文件全量字节保护，运行执行源码冻结后不改。安全的纯工具包装修复也须保存旧版并记原因/hash。
复核只根据当前ROOT的相对路径、Git ancestry、源码包、封存hash及纯数学审计，不要求旧磁盘路径或旧分支存在。
verify/report不调用生产放置器、MIP、Job.step或枚举新布局；新复算输出写新目录，不改原日志或hash清单。

## R4资格与保留方法差异

每场景Smart/FK/FKR共12格逐一校验：输入/order/80行/训练数据/共享GPU响应费用执行与allocator源，
以及各方法自身定义源码。Smart保留其原SmartGpuStage+比例配额适配，不要求它与GpuStage同类。
检查seed/间隔/H/batch/依赖/求解器hash，原80/80、真实原始资源/恢复/训练/JCT账本、来源快照/hash、
无wall计入JCT和无影响轨迹的截断/异常。外层上限不同但均正常结束不单独排除。
合格才REUSED_R4；新格NEW_EXECUTION_R6。不可比/未验证理由保留，比较留空，不追加12次重跑。
历史wall只单列参考，不计算跨机器/测量环境倍数。

## 指标与机制的预注册口径

完整80/80且audit PASS才计算mean/median/P95/P99 JCT、makespan、完整配对和总等待/训练/恢复。
JCT=完成−原到达；makespan=最后完成−最早到达；numpy.quantile(method=linear)。
改善率100*(baseline−method)/baseline；配对容差1e-7秒，资源/完整Allocation容差1e-7，score EPS沿原1e-9。
主要比较Direct/F-only、F-only/Smart、Direct/Smart、Direct/FK、Direct/FKR。
F-only/Smart为系统组合差异，不称严格CPU/RAM单因素因果估计。比值不是独占slowdown。
完整决策含GPU至commit，median/P95/P99/max，总轮/非空轮分开；inclusive嵌套不重复相加。
恢复取executions实际消耗，不累加重复remaining；启动/恢复/配置变化/纯物理节点迁移/aux-only分开。

同状态已完成D非空轮精确分解R=sum rho、L=sum rho*min(delay/180,1)、Phi=R−L；
核对DeltaPhi=DeltaR−DeltaL。normalized rho不是samples/s或JCT贡献百分比。
raw rho增加、总delay减少、R/delay相等但Phi变化、raw增益被恢复抵消等标志可重叠，不相减推断机会。
F选择区分严格Phi、delay/changes平局规则、完整最终平局、D预算回退；平局再分完整Allocation同/异。
CPU单变/RAM单变/联合变化/配额变rho不变分别记录；共同分配器RAM条件收益与Direct额外RAM作用分开。
CM是组合受控响应，不是RAM单因素或硬件实测；未观察到RAM额外增益就写未观察到。

案例固定：每场景首个D严格Phi增益；首个raw增益被恢复抵消；Direct对F-only最大**绝对**正JCT退化，
平局job_id。不符合就写无，不挑更好看案例。含后续真实GPU/batch/配额/训练/恢复轨迹，非单步严格因果。
无多seed、不用调度轮制造显著性、不把四画像条件说成四条独立生产trace。

## 实际入口

在当前仓库根与独立Python3.10环境中：

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts/run_direct_eval_r6.py --manifest configs/experiment_manifest_direct_eval_r6.json
# 明确中断恢复才加--resume；不删除预算或覆盖已有目录。
.\.venv\Scripts\python.exe -X utf8 -B scripts/verify_direct_eval_r6.py --manifest configs/experiment_manifest_direct_eval_r6.json
.\.venv\Scripts\python.exe -X utf8 -B scripts/report_direct_eval_r6.py --manifest configs/experiment_manifest_direct_eval_r6.json
```

预算内自动verify/report加--budgeted。交付后用户手动只读重建不启动新训练、不重置本轮账本。
本轮结束本地提交；手动push `git push -u origin capra/direct-evaluation-r6`，不自动推送。
