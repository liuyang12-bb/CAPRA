# CAPRA Direct R5 实现与验证报告



**实现已完成；限定验证完成。正式性能实验 NOT_RUN。** 两个固定smoke均正常退出、事件完整且独立审计通过；Smoke1为PARTIAL_SMOKE，不能称两者均完成全部作业。



基准`ffa953fb9cd12773992559512d85065bbd26b7b2`；独立分支`capra/direct-placement-r5`；方法CAPRA-Direct；版本CAPRA_V2_DIRECT_R5；本轮不推送。



## 1. D直接构造与F参考



D以真实恢复锁的完整Allocation/remaining起步；从不含node字段的GPU contract获得非锁作业，一次确定(len(A),-g,-round(pressure,12),job_id)顺序。每步先做比例保留+真实锁资源的布尔可完成性，再调用原RepairAllocator重配整个目标节点；以整节点rho×恢复有效窗口的delta选物理节点。所有合法delta非正也继续放完。D不调用旧K/R/S、finish、stabilize或swap；节点从评分到commit不变。



F先对独立witness副本运行原identity.reference，再用同一个RepairAllocator实例分配完整配额并评分。F先完成并验证，作为完整比较候选及协作式预算中止保护；D不使用F分组初始化、排序或候选限制。F配额之后不再搜索节点身份。所选Phi>=F-EPS只保证本轮模型分数，不保证长期JCT或公平性。



R4已存在节点raw sum-rho增量与资源分配，本轮不将它冒充新增。新增点是独立直接构造、一次排序、包含真实锁辅助资源的完成性、恢复加权整节点delta以及F/D身份分流。



## 2. 继承模块与新代码位置



|文件|入口|职责|
|---|---|---|
|[src/capra/placement_direct_r5.py](../src/capra/placement_direct_r5.py)|DirectPlacement.select/prepare_f/construct_d|F-only reference、单实例分配器trace/cache、一次排序、delta选择和完整比较/协作预算|
|[src/capra/feasibility_direct_r5.py](../src/capra/feasibility_direct_r5.py)|check_scope/can_finish|真实锁与比例保留、有效GPU容量、两箱布尔DP|
|[src/capra/runner_direct_r5.py](../src/capra/runner_direct_r5.py)|decide/run|GPU一次、live状态与contract检查、commit一次、原Job.step执行与新原始日志|
|[src/capra/audit_direct_r5.py](../src/capra/audit_direct_r5.py)|possible/audit_selection/audit|独立二维DP、排序/delta/费用/最终物理节点/执行账本复算|
|[tests/test_direct_r5.py](../tests/test_direct_r5.py)|DirectTests|13组A-G针对性测试，测试fixture与正式输入隔离|
|[scripts/run_direct_r5_validation.py](../scripts/run_direct_r5_validation.py)|main|原进程树管理+持久900秒账本+两个固定smoke|
|[scripts/verify_direct_r5_delivery.py](../scripts/verify_direct_r5_delivery.py)|child/main|同账本中的针对性测试补充与终检，支持旧attempt源码包保留|


原GpuStage/SiaPolicy、Responses/V2Responses、RepairAllocator/NodeAllocator/RAM修复、costs.transition/evaluate、identity.reference、commit_v2、Job.step和训练独立审计均复用；所有原文件字节保留，旧入口、审计白名单和method含义未改。独立runner只保留必要事件循环适配，未复制GPU优化器或另造恢复/训练系统。



## 3. 针对性测试与失败透明度



最新测试：13组，失败0、错误0、跳过0；全部通过。首轮已通过；终检补充不可行/纯GPU碎片边界后，只重跑测试，未重复smoke。两次测试均留档，没有真实实现失败或失败后隐藏重跑。



独立穷举检查82个极小状态，其中22个不可行，最多5作业、每状态最多8种完整赋值。含真实锁4GPU/20CPU使有效余量仅1GPU，以及6+6余量却无法容纳三个4GPU作业的纯碎片例。这里只是测试oracle，没有进入线上DP或额外正式实验。



最多三个唯一隔离fixture同状态F回放，与R4原F的完整配额和score完全一致；测试复验重复这三状态，不新增状态或历史闭环。字典顺序和合法witness/F节点改变时，D顺序、节点、分数与算法轨迹不变。旧K/R/finish禁调用且stabilize只由F reference调用一次。GPU/commit各一次、候选不调用Job.step；变GPU数量与物理节点只收一次原50秒转换费。



独立审计分别拒绝人为篡改delta、delay和最终节点的日志。预算中断用测试假时钟覆盖“尚未完成当前作业候选”和“已有完整前缀”两种情况；F-only跨预算也有覆盖。假时钟不是开销测量，实际smoke无预算回退。故意非法完整witness必须抛异常，未将其吞成PASS。



## 4. 冻结响应表互补机制fixture



TEST_ONLY：两台8GPU/24CPU/500GB，两个cifar10+两个bert各4GPU，启动费统一0以隔离机制。现有responses_original和原RepairAllocator产生F同类共置sum-rho=4，D直接构造AB/AB的sum-rho=5.06；每节点cifar10得到20CPU/250GB、rho1.53，bert得到4CPU/83.32GB、rho1。该布局在D构造阶段形成，之后没有swap/stabilize。普通旧作业确实可移动，peer临时超额配额可以回收。这是机制正确性测试，不能当作生产收益百分比。



## 5. 两个固定短程smoke



|用例|输入/画像|状态|submitted/arrived/completed/unfinished|轮数|非空轮D完成/选D/选F|真实整树wall秒|
|---|---|---|---|---|---|---|
|smoke1|S7 dense05 / Original|PARTIAL_SMOKE|8/8/6/2|60|56/5/51|32.644885|
|smoke2|S8 dense05 / CM|COMPLETE_SMOKE|8/8/8/0|46|44/8/36|32.061489|


原文件前8行，不改arrival、不筛选任务；原cluster_cpu3、画像、成本和batch规则。每例最多60轮×60秒，内部90秒，外层120秒含清理，严格串行。



|用例|D完成后F较高Phi|F较小delay|F较少changes|完整平局F|预算回退|
|---|---|---|---|---|---|
|smoke1|1|0|0|50|0|
|smoke2|2|0|0|34|0|


非空调度共100轮，D完整构造100轮、选择D 13轮、正常F胜/平87轮，实际预算回退0，构造内部错误0。含空计划时共106轮，D构造106轮、选D13、选F93，不把空轮算作有意义的D收益。



Smoke1未完成2个作业，整体mean/P95/P99 JCT与makespan均为空。Smoke2全部完成，原始summary保留其前8作业的JCT，但本轮不做方法对照、不从这个值推导性能改善。两个smoke均有D被选择的真实路径，仍不能据此声称正式JCT优势。



## 6. 独立资源/费用/执行审计



原始events/start/termination/输出哈希与derived per_job/node_resources/direct_audit齐全。审计独立重算所有记录候选的初始A、preferred压力、一次排序、被拒绝及被接受节点的can_finish、peer加权贡献、delta和平局，复核F-only身份与D前缀/完整物理节点。完成性使用独立二维占用DP，不调用线上can_finish。



逐节点容量、画像合法域、比例性能保护、锁Allocation/remaining、GPU contract/batch、预测费用=commit费用、恢复与训练分离、rho单次作用及JCT守恒全部通过。程序异常会直接中止验证用例并写failure，不吞成F成功。本轮没有发生该类异常。



## 7. 实际开销与缓存计数



|用例|决策median/P95/P99/max秒|F-only reference P95|F quota P95|D构造P95|审计秒|
|---|---|---|---|---|---|
|smoke1|0.031305/0.060317/0.091575/0.115241|0.000640|0.005906|0.013836|2.136209|
|smoke2|0.030125/0.066298/0.079589/0.084741|0.000649|0.007344|0.019936|2.097119|


GPU、F reference、F quota、D和commit为外层顺序区间；完成性、allocator和scoring为嵌套区间，不能相加或机械相减。全部wall独立报告，未扣入模拟JCT。实际smoke没有跨5秒，原子调用与F准备仍可能在其他负载超出协作预算，未声明5秒硬保证。



非空轮累计solve请求1274、冷计算1069、cache hit205、布尔DP检查1072、preferred调用486、画像查询50299（hit=48946,miss=1353）。逐轮均满足D after<=2M、总solve请求<=2M+2N；真实node ID+排序job set作为原单轮cache key，不跨轮共享依赖current/locks的配额缓存。明细见analysis/round_metrics.csv和原始allocation_traces/solve_requests。



## 8. 预算、整体时长与进程清理



累计验证命令wall（含启动、退出和所属进程树清理）163.695141/900秒，剩余736.304859秒。初始测试、补充测试、两个smoke和两次终检均在同一账本留档，不重置。编码阅读文档不计此预算；快照/报告只读统计没有推进任何训练或额外状态搜索。



从独立环境准备开始至本报告的实测端到端1493.96秒，其中验证163.70秒，阅读/编码/文档/编排约1330.26秒；该计时标记前的首次提示词阅读和worktree创建未单独计时，不能伪称完整请求总耗时的精确测量。最终封存时长另见delivery_clock.json与Git本地交付回执。所有已启动命令正常退出，所有owned cleanup.active_after_cleanup=0，无后台实验进程遗留。



## 9. 当前限制与下一步



继承的辅助分配器依旧是有限候选上的raw-rho启发式+RAM补充，未改成节点内恢复加权全局优化；本轮恢复加权发生在节点布局选择层。无完整GPU类型/batch条件画像、节点内全局最优、GPU/辅助资源全局联合最优、端到端JCT或长期公平性保证。只验证当前单节点/每类型最多两节点；未实现扩容。



用户审查此实现后，下一阶段另行预注册正式对照及硬预算，再评估Direct相对FK/FKR/Smart的JCT、尾部、恢复和开销。本轮不自动开正式矩阵、不搜索有利场景或调画像/费用/H以追求提升。



## 10. 交付入口、复现与本地提交



- 根入口：DIRECT_R5_README.md。

- 精确代码：src/capra/*direct_r5.py、tests/test_direct_r5.py及scripts相应入口。

- 设计：docs/CAPRA_DIRECT_R5_DESIGN.md。

- 原始日志：runs/direct_r5/validation/direct_r5_fixed_validation/。

- 预算：runs/direct_r5/validation_budget.json；最终核验：runs/direct_r5/final_evidence_checks.json。

- 结果分析：runs/direct_r5/analysis/implementation_results.json、round_metrics.csv。

- 首次和补充测试的fixture/篡改拒绝/三个F回放均在各tests/attempt*/artifacts。

- 旧attempt源码包在runs/direct_r5/snapshots，文件修订在development/revisions，不覆盖。



基准分支本地HEAD尚为基准时完成源/历史核验，随后只提交新增R5文件；最终提交号由`git rev-parse HEAD`和交付回复提供，避免把提交自身哈希嵌入其内容形成循环。未推送/合并/创建PR。



手动续作固定验证（账本不重置，已通过同源attempt可复用）：



```powershell

$env:PYTHONPATH="$PWD/src"

$env:PYTHONUTF8="1"

$env:OPENBLAS_NUM_THREADS="1"

$env:OMP_NUM_THREADS="1"

$env:MKL_NUM_THREADS="1"

$env:NUMEXPR_NUM_THREADS="1"

$env:PYTHONHASHSEED="0"

.\.venv\Scripts\python.exe -X utf8 -B scripts/run_direct_r5_validation.py --resume

```



已有输出不能覆盖；独立重新验证须新预登记run_id与账本，不能删本轮账本获得额外预算。单次运行示例只作未来手动复现，当前不执行：



```powershell

.\.venv\Scripts\python.exe -X utf8 -B -m capra.runner_direct_r5 --method CAPRA-Direct --allocator-mode ram_slack_v1 --input data/pressure_r4/saturn7_dense05.csv --cluster data/scenarios_r1/cluster_cpu3.json --responses data/scenarios_r1/responses_original.json --output runs/direct_r5/manual-review-01 --max-jobs 8 --max-rounds 60 --interval 60 --wall-limit 90

```



手动推送：



```powershell

git -C "D:/科研启航/CAPRA-direct-placement-r5" push -u origin capra/direct-placement-r5

```


