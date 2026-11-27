# CAPRA R4：冻结算法下的压力与R机会诊断预注册

唯一基准5af0bdb6b86b797225908f717b5b9324cd48a539；独立capra/pressure-opportunity-r4。完整授权原文CAPRA_R4_EXECUTION_ORDER.txt。全部2543基准跟踪文件保护；R3算法模块和旧日志一律原字节，不改MELD，不推送远端。

研究问题：到达增密是否提高各GPU池竞争/排队/共置机会；匹配smart位置保留后FK资源增量是否存在；FKR对FK均值/尾部/迁移/开销如何；R机会在同型、装箱、参考已覆盖、锁、候选覆盖、净评分、动态执行哪层受限。增密不承诺帮助R。

## 输入与唯一12格

只从R3的Saturn7/8 supported80派生：Decimal精确`t0+(ti-t0)/2`，保留原t0、原行顺序、任务身份及全部非time字段。相同时刻按原行号稳定顺序。目标Saturn7 dense05首末225/11498秒，Saturn8为90/11309.5秒（均须实际核验）。保存逐行映射、源/派生/生成器SHA、间隔分布、应用和请求GPU分布。称压力派生场景，不称新独立holdout。

顺序预定：Saturn7 Original Smart→FK→FKR，再CM Smart→FK→FKR；Saturn8 Original FKR→FK→Smart，再CM FKR→FK→Smart。12格全部实际运行，无等价复用。内部方法CAPRA即完整F/K/R，报告显示CAPRA-FKR。Smart=比例/none；FK与FKR=ram_slack_v1。R3原场景只读HISTORICAL_REFERENCE，不计新增执行。

40GPU/6节点、每类型两节点、4/8GPU、CPU3/GPU、RAM62.5GB/GPU、原节点ID和全部容量不变；原GPU MIP/在线性能/批大小/实际恢复费/物理锁/commit、H180、EPS和平局、NodeAllocator与RAM规则不变。Original/CM引用R3冻结哈希，非RAM单因素消融。seed0、周期60秒、6000轮、原依赖和线程1。

仅新增R4入口、独立审计、确定性输入、只读诊断和计时：TimedAllocator代理原baseline/solve/layout，原样转发参数和返回，仅累加perf_counter及请求数；无随机/排序/响应查询副作用，包含于原决策开销。GPU沿用原GpuStage/SmartGpuStage。identity计时为原reference及mapping+scoring；allocator计时含对应原路径；R及RAM计时嵌套；MIP/setup/solve优先读取原stdout中逐次Solver took记录并核对数量，不可可靠对应时标不可得，不能假造精确MIP独占时间。审计本身计时独立，不计模拟JCT。

## 验证与预算（首次测试前固定）

首次R4验证前建立10800秒连续单调预算，前期阅读/初步开发单列。验证：原40测试及新增数据/计时透明性/严格漏斗/拒绝性；R3三方法×四条件，各取前2/后2非空、首次K/R选中、首次锁、首次K不可行，先登记所有状态再回放，排除计时/新增r4_字段。GPU计划/batch/锁/费用/布局/配额/Phi/选择保持；冻结Job.step源和原训练分段独立账本验证继续保留。最多两次12作业/30轮、内90秒外120秒短冒烟（已开发W2 smart original、CAPRA CM），内部Job.step逐次登记。无完整旧负载重跑。

Windows Job Object挂起创建后归属再恢复，验证孙进程清理；只终止所属树。每格runner900秒、所属树960秒、全局剩余减至少30秒；原STOP_REQUEST、全部到达后30轮无进展、三次非空>30秒保持。所有测试/验证/冻结/正式/审计和有限离线状态诊断均由同一deadline约束，不重置。无正式自动重试；严重正确性失败即停止后续，保留FAIL/INCOMPLETE/NOT_RUN。会话恢复只读验证完整且哈希相同的COMPLETE_PASS；未封闭RUNNING作为INCOMPLETE不重新运行。纯离线统计绘图报告另计，不启动新模拟或额外状态搜索。

## 机会漏斗的可检验定义

统一分母为每格全部非空GPU计划轮次N，逐轮只计0/1、任务对以排序job_id去重；同时保留逐轮证书和非互斥标签。严格嵌套不是把重叠边际计数相减。

A=本轮非空完整GPU计划；B=存在同GPU类型CPU或RAM donor/receiver互补任务对（原响应轴合法比例点判据）；C=B中某对GPU数量总和能容纳于同型节点；D=C中某对尚未在任何可行F/K（smart用P）共置；E=D中某对存在一个不改变其他任务节点的直接单任务搬移见证，锁原样、全任务集GPU/比例基线+精确锁CPU/RAM容量和画像合法。E为当前共同保留规则下的充分证书，不通过不证明不存在其他优化布局；记录最小配额/借用锁/碎片及GPU池等失败标签。

F=实际记录的R候选可行、布局覆盖某E任务对；FK/Smart按协议不生成R，F后为0并标协议不适用，不声称算法漏掉。G=F且R的未扣恢复sum-rho优于最佳F/K（同一冻结分配器实际评分，保留gross、净Phi和费用各列）；H=G且扣费Phi/原平局规则实际选R；I=H且当轮真实训练含正辅助倍率收益。R仅靠减恢复而入选、R入选却不属于此“新共置”漏斗等另列标签。I不等于动态JCT改善；全部R选择和逐作业轨迹另报。

非互斥标签：不同GPU池、缺少互补、GPU和/碎片/当前比例保留CPU或RAM不足、锁、参考已共置、R协议未生成/R不可行/R未覆盖、gross不足、净Phi不足或费用抵消、cost-only R、R已选但全程作业退化。D的定义限定“新共置”；参考已共置但配额或其他布局仍可能有机会，不能宣称全局完备。

## 有限候选覆盖审查（预算内，不进正式算法）

每个R4条件只取FKR轨迹的前一个E成立但R未覆盖或gross无增益的小状态、和前一个R入选的小状态，去重；小状态要求总计划任务<=6、未锁<=4，每型两节点，最多2^4=16布局/状态，四条件最多8状态/128布局。只枚举未锁任务同型节点，保留所有GPU配置/batch/任务/锁，原NodeAllocator+ram_slack_v1及identity/评分重新求每个布局；记录完整可行性、Phi、sum-rho、费用、候选哈希与R是否覆盖。无符合状态明确记空，不另改规则填满。不称全局JCT最优。

历史解释只读R2 CM正收益与R3 Saturn8 CM负收益，按首次R入选/配对最坏退化附近轮次确定代表；不重跑旧实验。R4每条件若有R选择，取FKR/FK最差相对退化的、确实涉及R的任务，保存R轮/节点/配额/预测rho与费用、后续GPU变化、实际训练/恢复/JCT。动态轨迹分化，账本差非单轮因果。局部枚举属于预算内诊断；最终纯报告阶段不得追加。

## 统计口径与研究决定

完整80/80才给全体mean/median/P95/P99/makespan；不完整全部为空，submitted/completed/censored/剩余名单保留。对同压力同画像主比较FK/Smart、FKR/Smart、FKR/FK，改善100*(1-method/base)，正负均保留。R3压力前后只场景敏感性，不当算法贡献或独立样本。每节点/类型/全局GPU/CPU/RAM积分都含恢复，以共同[最早到达,最后完成]窗口容量时间为分母；队列/活跃时序按真实到达和完成、区分尚未到达。CPU/RAM条件差不可相加当总收益。输出训练加权rho、迁移/费用/候选、开销median/P95/P99/max/>5秒与各层嵌套计时。

只根据12格和诊断证据建议FK或FKR或保留并行，并排序80GPU/160作业扩容、Synergy-TUNE公平适配、画像误差/少量实测与R针对性改进。不在本轮实施R5/R6，不以删除两节点断言扩容，不把合成敏感度称为硬件实测。
