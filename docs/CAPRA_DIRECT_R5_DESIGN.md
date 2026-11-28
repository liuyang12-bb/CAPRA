# CAPRA Direct R5 设计与验证预登记

基准：`ffa953fb9cd12773992559512d85065bbd26b7b2`；独立分支 `capra/direct-placement-r5`。
方法 `CAPRA-Direct`，运行版本 `CAPRA_V2_DIRECT_R5`，候选只有 **F/D**。
本轮是实现与正确性接入交付，正式性能实验 **NOT_RUN**，不自动推送。

## 输入、范围与继承

保持所有基准已跟踪文件字节不变，包括旧入口、旧审计白名单、画像、输入与结果。
单作业单节点；每 GPU 类型至多两节点。实际读取每节点 GPU/CPU/主机 RAM 容量。
不新增 S、K、R、局部 move/swap 或多顺序搜索。两箱 DP 仅用于布尔完成性。
H=180、周期60秒、seed0、数值线程1。辅助分配复用原 `RepairAllocator/ram_slack_v1`。
画像仍是按每 GPU 查询的冻结归一化 CPU/RAM 模板，不新增类型/batch 条件硬件实测。
Sia GPU MIP、goodput/在线投影、batch、恢复锁、恢复成本和训练执行原样复用。

## 每轮不可变契约与 F/D 分流

GPU 阶段使用原 `GpuStage(...,uniform_costs=True)` 一次，保存 raw plan 和锁修复完整 witness。
契约只保留每个作业的 `name/gpu_type/gpus/nodes/atomic_bsz/accum_steps`，不含参考 node。
SHA256 在候选前、候选后和 commit 前核对；候选前后比较 live Job 快照。
放置器对 GPU contract 构造 node 为空的 plan，D 和共享 allocator 均无法从该字段取得 F 分组。
current/locks/remaining/started/apps/nodes/画像内容整轮冻结；查询缓存只保留既有语义。

F 先在独立 witness 副本上调用一次原 `identity.reference`。按其节点分组调用共享 allocator，
得到完整合法配额后用原 `costs.evaluate` 评分；F 配额完成后不再 identity 搜索。
D 只以真实锁的 Allocation/remaining 初始化；普通运行作业不硬固定，也无上一轮额外配额权利。
F 只作为已验证完整保护方案与最终比较候选，不作为 D 构造初始布局。
F 和 D 都以同一真实 current 计费，绝不把 F 或前一个 trial 当作执行状态。

## 一次排序

只在真实 locks 固定的初始状态，逐作业求所有可完成剩余契约的同类型合法节点 A_j。
联合 preferred 点来自原 `response.preferred(app,g,node)`，不会拼接两个不同最优点。

`pressure(j,n)=max(0,preferred_cpu/C-g/G,preferred_ram/M-g/G)`；`pressure(j)=max_n pressure(j,n)`。

只排序一次：`(len(A_j),-g_j,-round(pressure(j),12),job_id)`。
节点候选始终按实际 node ID 顺序遍历，不动态重排剩余作业。

## 布尔可完成性

已放锁扣实际 GPU/CPU/RAM；已放非锁和未放非锁使用目标节点比例配额保守预留。
先检查部分容量和画像合法域，再用小整数枚举有效剩余 GPU 容量 b_n。
比例预留可以回收临时优化的超比例配额；恢复锁的完整配额不能回收。
一个节点检查总 GPU 与逐作业合法域；两个节点使用有限可达占用 DP，
每次转移检查左右容量，最终检查另一箱占用。不同 GPU 池独立。
无跨轮布尔缓存，不会发生仅按总 GPU 的缓存混淆；不返回优化布局。
超过两节点/多节点作业明确 `UNSUPPORTED_SCOPE`，不静默截断。

关键测试：两台8GPU/24CPU/500GB，n0锁4GPU/20CPU/250GB时 b0=1；
剩余[4,4,1]只能将1GPU放n0，若先把它放n1必须拒绝该前缀。

## 整节点恢复加权增量

当前节点前缀的 before 配额/分数直接复用；对加入 j 的 after 调用一次原节点分配器，
重新分配该节点所有非锁作业配额，检查合法域与目标节点比例性能下界。

`U_n(A)=sum_i rho_i*max(0,1-delay_i/180)`；`delta=U_n(after)-U_n(before)`。
delay 始终使用原 transition 对真实 current/locks/remaining/started 计算。
所有受影响 peer 都进入 delta；不重复扣恢复费，不以 raw sum-rho 排名。
同 GPU 配置与节点同时变化，沿用一次原转换成本。

节点比较：delta(EPS) → 插入作业新增恢复成本 → current 原节点 → node ID。
全为负/零也要选最好节点继续，不能拒绝 GPU 阶段选中的作业。
已选前缀节点不再移动，后续可回收和重新分配其 CPU/RAM。
最终合并最后保存的节点结果，不重复求解，不再 stabilize/swap。

完整 F/D 比较：Phi(EPS) → total_delay → 原 evaluate.changes → 完全平局 F。
仅保证所选本轮模型 Phi>=F-EPS，不保证端到端 JCT 或长期公平性。

## 缓存、计时和预算

每轮新建一个原 RepairAllocator；F/D共享实例，cache key保留真实node与排序job set。
初始锁集合和F每节点至多一次，D每作业至多两个 after 请求，总请求<=2M+2N。
before/已选 after 保留 trace ID，不重复调用；冷计算、请求与cache hit分别记录。
初始 A_j 与逐步完成性共至多约4M+1次布尔检查；画像首选点至多2M次。
有限两箱状态数由GPU容量限制；节点分配仍是原有限启发式，非全局最优。

协作式5秒包含F reference/F配额/排序/完成性/allocator/评分。
F必须先完整构造并验证；F耗尽预算则 `D_NOT_STARTED_BUDGET`。
D有界步骤和昂贵调用前检查，超时记录 `D_BUDGET` 和真实前缀，提交已验证F。
单次原子调用可能超额，记录实测超额；不能声称严格5秒硬上限。
内部断言/异常直接抛出并记失败，不吞成 F_SELECTED/PASS。
完整决策时间含GPU、F、D、commit；细分计时有嵌套，禁止重复相加。

## 独立审计与验证边界

独立审计不导入 DirectPlacement/can_finish/allocator：用独立二维占用DP核对可完成性，
从原事件重算联合 preferred、压力、排序、全部合法/拒绝候选、peer贡献、delta及平局。
RAM修复和训练账本复用既有独立公式审计。只选择完整候选，只commit一次；
逐任务预测费用与commit一致，倍率只加速训练一次，恢复不受rho加速。
通过trace ID保留所有冷配额和RAM修复证据，不把缓存命中伪装成冷求解。

针对性 A-G 测试含真实表互补 fixture、负增量、成本对比、真实锁有效容量、
小状态独立穷举、字典/参考节点不变性、最多三个唯一 F 同状态回放、
GPU/commit一次与篡改delta/delay/最终节点拒绝。fixture不进入正式data/画像。

验证串行，持久累计命令实际wall总预算900秒，包含启动、退出和所属树清理。
复用原Windows Job Object，不杀无关进程；外层120秒含清理，预留21秒，
执行阶段在99秒前终止，内部90秒；剩余不足时缩短。每次attempt保留源码包/hash及原始日志。
未闭合attempt保守扣满允许外层预算，重启不重置；失败后只允许同固定用例正确性修复重试。

唯一两个 smoke：S7 dense05 Original、S8 dense05 CM；原cluster_cpu3输入字节；
各按原文件前8行、60轮、60秒周期。未完成整体mean/P95/P99/makespan为空。
状态区分 COMPLETE_SMOKE/PARTIAL_SMOKE/EXTERNAL_TIMEOUT/NOT_RUN/FAILED。
smoke只验证接入执行，不作论文性能改善证据。正式矩阵 **NOT_RUN**。

## 调用关系与复现

`runner_direct_r5.decide → GpuStage.choose → DirectPlacement.select → F-only reference + shared RepairAllocator → direct construct → complete compare → commit_v2`。
之后原Job.step推进训练；`audit_direct_r5`独立核对放置、费用、真实执行和JCT账本。
旧GPU/成本/身份/分配器/执行/runner/审计文件不改，新runner保留最小事件循环适配以避免放宽旧白名单。

```powershell
$env:PYTHONPATH="$PWD/src"
$env:PYTHONUTF8='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
$env:PYTHONHASHSEED='0'
.\.venv\Scripts\python.exe -X utf8 -B scripts/run_direct_r5_validation.py
# 账本已存在时，仅按明确的正确性修复续作；不能删账本重置预算：
.\.venv\Scripts\python.exe -X utf8 -B scripts/run_direct_r5_validation.py --resume
```

未解决：完整GPU类型/batch条件画像、节点内全局最优、GPU/辅助资源全局联合最优、
端到端JCT/长期公平性保证。本轮不实现扩容/外部基线，也不以烟测胜负调参。
