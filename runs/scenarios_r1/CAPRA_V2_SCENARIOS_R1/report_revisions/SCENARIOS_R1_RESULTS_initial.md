# CAPRA v2：六个优化机会场景的受控实验结果

本轮只改变输入场景及其运行/审计接口，保持v2调度策略字节不变。基础提交 `0b87934ae558960921889b01d14502155fb0c41c`；新版本 `CAPRA_V2_SCENARIOS_R1`；本地分支 `capra/scenarios-r1`。原v1/v2成果保留，无远端推送。

正式格完成：18/18；完成作业：1440/1440。每格状态、删失和错误均保留在results.csv/json。只有完整80/80才报告全体JCT分位数。

## 原v2六格参考（不是新矩阵的一部分）

|原负载|方法|mean|P95|P99|
|---|---|---:|---:|---:|
|original_w2|SIA-P|1056.11|3088.15|3800.98|
|original_w2|CAPRA-Fixed|971.02|2990.45|3759.56|
|original_w2|CAPRA|949.46|3264.05|4157.23|
|original_w6|SIA-P|1056.55|2794.10|3298.29|
|original_w6|CAPRA-Fixed|973.73|2777.55|3652.58|
|original_w6|CAPRA|911.48|2804.15|3296.77|

原六格通过复制件独立原始审计；原结果目录不写回。W2原CAPRA对SIA-P的P95/P99增加约5.70%/9.37%，仍然保留。原RAM比例以上饱和、BERT训练份额低和DS比例已饱和形成了本轮研究动机，不是新实验必胜目标。

## 新六场景十八格

时间单位为模拟秒。改善率=100×(1−method/baseline)，正数表示更快；比较仅限同场景同版本。

|场景|方法|完成/状态|mean|P50|P95|P99|makespan|
|---|---|---|---:|---:|---:|---:|---:|
|w2_dense_original|SIA-P|80/80 ALL_COMPLETE|1774.46|1558.00|5257.32|6062.61|10895.00|
|w2_dense_original|CAPRA-Fixed|80/80 ALL_COMPLETE|1694.30|1531.50|5210.82|6139.34|10948.00|
|w2_dense_original|CAPRA|80/80 ALL_COMPLETE|1462.99|1168.50|5026.30|5400.93|10510.00|
|w6_dense_original|SIA-P|80/80 ALL_COMPLETE|1487.47|1184.25|3613.57|5096.30|11740.00|
|w6_dense_original|CAPRA-Fixed|80/80 ALL_COMPLETE|1372.79|1017.00|3368.05|4924.84|11648.00|
|w6_dense_original|CAPRA|80/80 ALL_COMPLETE|1170.88|802.75|3213.37|4513.17|11636.00|
|w2_dense_cpu2|SIA-P|80/80 ALL_COMPLETE|2801.55|2311.00|9106.02|9789.83|14165.00|
|w2_dense_cpu2|CAPRA-Fixed|80/80 ALL_COMPLETE|2615.05|2183.75|8352.73|9500.77|13944.00|
|w2_dense_cpu2|CAPRA|80/80 ALL_COMPLETE|2359.53|1979.75|8182.27|8762.99|13485.00|
|w2_dense_cpu6|SIA-P|80/80 ALL_COMPLETE|1028.35|611.00|3963.95|5085.30|10598.00|
|w2_dense_cpu6|CAPRA-Fixed|80/80 ALL_COMPLETE|1037.03|558.75|4325.12|4963.28|10543.00|
|w2_dense_cpu6|CAPRA|80/80 ALL_COMPLETE|905.65|497.50|4014.85|4598.17|10436.00|
|w2_dense_cn|SIA-P|80/80 ALL_COMPLETE|1774.46|1558.00|5257.32|6062.61|10895.00|
|w2_dense_cn|CAPRA-Fixed|80/80 ALL_COMPLETE|1584.44|1283.25|5064.27|5740.97|10675.00|
|w2_dense_cn|CAPRA|80/80 ALL_COMPLETE|1403.04|1095.50|4586.87|5290.07|10569.00|
|w2_dense_cm|SIA-P|80/80 ALL_COMPLETE|1774.46|1558.00|5257.32|6062.61|10895.00|
|w2_dense_cm|CAPRA-Fixed|80/80 ALL_COMPLETE|1467.22|1176.00|4544.67|5382.48|10569.00|
|w2_dense_cm|CAPRA|80/80 ALL_COMPLETE|1380.94|1125.50|4259.22|5299.56|10650.00|

|场景|比较|mean改善%|P95改善%|P99改善%|恢复改善%|
|---|---|---:|---:|---:|---:|
|w2_dense_original|CAPRA-Fixed/SIA-P|4.52|0.88|-1.27|4.33|
|w2_dense_original|CAPRA/SIA-P|17.55|4.39|10.91|43.10|
|w2_dense_original|CAPRA/CAPRA-Fixed|13.65|3.54|12.03|40.52|
|w6_dense_original|CAPRA-Fixed/SIA-P|7.71|6.79|3.36|10.01|
|w6_dense_original|CAPRA/SIA-P|21.28|11.07|11.44|36.52|
|w6_dense_original|CAPRA/CAPRA-Fixed|14.71|4.59|8.36|29.46|
|w2_dense_cpu2|CAPRA-Fixed/SIA-P|6.66|8.27|2.95|7.83|
|w2_dense_cpu2|CAPRA/SIA-P|15.78|10.14|10.49|42.12|
|w2_dense_cpu2|CAPRA/CAPRA-Fixed|9.77|2.04|7.77|37.20|
|w2_dense_cpu6|CAPRA-Fixed/SIA-P|-0.84|-9.11|2.40|-1.92|
|w2_dense_cpu6|CAPRA/SIA-P|11.93|-1.28|9.58|23.80|
|w2_dense_cpu6|CAPRA/CAPRA-Fixed|12.67|7.17|7.36|25.24|
|w2_dense_cn|CAPRA-Fixed/SIA-P|10.71|3.67|5.31|6.30|
|w2_dense_cn|CAPRA/SIA-P|20.93|12.75|12.74|40.46|
|w2_dense_cn|CAPRA/CAPRA-Fixed|11.45|9.43|7.85|36.46|
|w2_dense_cm|CAPRA-Fixed/SIA-P|17.31|13.56|11.22|18.22|
|w2_dense_cm|CAPRA/SIA-P|22.18|18.98|12.59|33.92|
|w2_dense_cm|CAPRA/CAPRA-Fixed|5.88|6.28|1.54|19.19|

![Mean JCT](../runs/scenarios_r1/CAPRA_V2_SCENARIOS_R1/figures/mean_jct.png)

## 时间分解与完整决策开销

|场景|方法|等待|训练|恢复|决策median|P95|max|格wall|
|---|---|---:|---:|---:|---:|---:|---:|---:|
|w2_dense_original|SIA-P|69.53|1368.81|336.12|0.0661|0.1699|0.3263|190.45|
|w2_dense_original|CAPRA-Fixed|56.02|1316.71|321.56|0.0747|0.1902|0.2900|180.65|
|w2_dense_original|CAPRA|38.02|1233.71|191.25|0.1168|3.2497|3.4523|295.97|
|w6_dense_original|SIA-P|35.72|1099.06|352.69|0.0511|0.2272|0.3347|241.64|
|w6_dense_original|CAPRA-Fixed|34.97|1020.45|317.38|0.0635|0.2563|0.4224|236.36|
|w6_dense_original|CAPRA|32.72|914.29|223.88|0.1040|2.3473|3.6162|311.70|
|w2_dense_cpu2|SIA-P|197.03|2176.15|428.38|0.0803|0.2215|0.3823|210.22|
|w2_dense_cpu2|CAPRA-Fixed|132.53|2087.71|394.81|0.0764|0.2167|0.3211|200.34|
|w2_dense_cpu2|CAPRA|105.53|2006.06|247.94|0.1884|4.7243|5.9478|470.95|
|w2_dense_cpu6|SIA-P|32.02|768.14|228.19|0.0547|0.1207|0.2651|220.29|
|w2_dense_cpu6|CAPRA-Fixed|32.77|771.69|232.56|0.0598|0.1695|0.2574|207.07|
|w2_dense_cpu6|CAPRA|29.02|702.75|173.88|0.0950|0.8910|1.4601|249.31|
|w2_dense_cn|SIA-P|69.53|1368.81|336.12|0.0672|0.2050|0.3123|207.82|
|w2_dense_cn|CAPRA-Fixed|41.02|1228.47|314.94|0.0795|0.2332|0.3432|198.99|
|w2_dense_cn|CAPRA|40.27|1162.64|200.12|0.1256|2.6415|3.1158|311.38|
|w2_dense_cm|SIA-P|69.53|1368.81|336.12|0.0649|0.1819|0.3278|206.59|
|w2_dense_cm|CAPRA-Fixed|43.27|1149.08|274.88|0.0694|0.1936|0.3103|198.80|
|w2_dense_cm|CAPRA|40.27|1118.54|222.12|0.1132|2.9560|3.8425|322.74|

开销主口径仅非空决策，包括GPU准备/MIP、参考映射、候选/配额、稳定评分、校验及提交。all_rounds另见各analysis_r1/opportunity_metrics.json。控制器wall不计入模拟JCT，真实恢复计入。训练加权指标来自实际训练段。

![Time accounting](../runs/scenarios_r1/CAPRA_V2_SCENARIOS_R1/figures/time_decomposition.png)

## 相对比例性能与CPU/RAM条件增益

rho_prop使用本场景所在节点的比例CPU/RAM。CPU条件差=rho(c,m)−rho(c_prop,m)；RAM条件差=rho(c,m)−rho(c,m_prop)。两者不能相加解释总收益，更不能直接换算动态JCT因果贡献。

|场景|方法|加权rho|加权rho/rho_prop|超过比例训练%|CPU条件差|CPU正训练%|RAM条件差|RAM正训练%|
|---|---|---:|---:|---:|---:|---:|---:|---:|
|w2_dense_original|SIA-P|1.0000|1.0000|0.00|0.0000|0.00|0.0000|0.00|
|w2_dense_original|CAPRA-Fixed|1.0460|1.0460|7.27|0.0460|7.27|0.0000|0.00|
|w2_dense_original|CAPRA|1.0513|1.0513|7.56|0.0513|7.56|0.0000|0.00|
|w6_dense_original|SIA-P|1.0000|1.0000|0.00|0.0000|0.00|0.0000|0.00|
|w6_dense_original|CAPRA-Fixed|1.0770|1.0770|14.22|0.0770|14.22|0.0000|0.00|
|w6_dense_original|CAPRA|1.0973|1.0973|15.86|0.0973|15.86|0.0000|0.00|
|w2_dense_cpu2|SIA-P|0.6994|1.0000|0.00|0.0000|0.00|0.0000|0.00|
|w2_dense_cpu2|CAPRA-Fixed|0.7268|1.0359|3.69|0.0255|3.69|0.0000|0.00|
|w2_dense_cpu2|CAPRA|0.7250|1.0343|4.66|0.0243|4.66|0.0000|0.00|
|w2_dense_cpu6|SIA-P|1.3219|1.0000|0.00|0.0000|0.00|0.0000|0.00|
|w2_dense_cpu6|CAPRA-Fixed|1.4266|1.0606|17.01|0.1061|17.01|0.0000|0.00|
|w2_dense_cpu6|CAPRA|1.4024|1.0610|17.28|0.1068|17.28|0.0000|0.00|
|w2_dense_cn|SIA-P|1.0000|1.0000|0.00|0.0000|0.00|0.0000|0.00|
|w2_dense_cn|CAPRA-Fixed|1.0985|1.0985|14.08|0.0985|14.08|0.0000|0.00|
|w2_dense_cn|CAPRA|1.0837|1.0837|10.78|0.0837|10.78|0.0000|0.00|
|w2_dense_cm|SIA-P|1.0000|1.0000|0.00|0.0000|0.00|0.0000|0.00|
|w2_dense_cm|CAPRA-Fixed|1.1396|1.1396|18.63|0.1056|14.92|0.0340|3.70|
|w2_dense_cm|CAPRA|1.1171|1.1171|15.47|0.0923|11.93|0.0248|3.54|

CPU6的rho>1不等于优于同场景比例；CPU2的rho=1可能已超过同场景比例。分应用条件增益、训练/GPU时间份额见opportunity_summary.json。占用积分逐节点及按GPU类型写入各analysis_r1/occupancy.csv，包含恢复，不能称硬件忙碌利用率。

## 布局、恢复与机会限制

|场景|方法|非空轮|选F/K/R或P|R原始rho高于F轮|R仅成本优势轮|纯节点迁移|aux更新|可用闲置资源机会轮|RAM候选漏点轮|
|---|---|---:|---|---:|---:|---:|---:|---:|---:|
|w2_dense_original|SIA-P|182|{'P': 182}|0|0|249|0|66|0|
|w2_dense_original|CAPRA-Fixed|183|{'F': 183}|0|0|229|46|0|0|
|w2_dense_original|CAPRA|175|{'F': 97, 'R': 8, 'K': 70}|7|54|24|45|0|0|
|w6_dense_original|SIA-P|196|{'P': 196}|0|0|223|0|102|0|
|w6_dense_original|CAPRA-Fixed|194|{'F': 194}|0|0|201|55|0|0|
|w6_dense_original|CAPRA|194|{'F': 132, 'R': 10, 'K': 52}|5|36|39|55|0|0|
|w2_dense_cpu2|SIA-P|236|{'P': 236}|0|0|363|0|57|0|
|w2_dense_cpu2|CAPRA-Fixed|233|{'F': 233}|0|0|314|38|0|0|
|w2_dense_cpu2|CAPRA|225|{'F': 111, 'R': 2, 'K': 112}|5|75|26|39|0|0|
|w2_dense_cpu6|SIA-P|177|{'P': 177}|0|0|115|0|92|0|
|w2_dense_cpu6|CAPRA-Fixed|175|{'F': 175}|0|0|125|51|0|0|
|w2_dense_cpu6|CAPRA|173|{'F': 133, 'K': 36, 'R': 4}|6|24|16|46|0|0|
|w2_dense_cn|SIA-P|182|{'P': 182}|0|0|249|0|66|0|
|w2_dense_cn|CAPRA-Fixed|178|{'F': 178}|0|0|245|105|0|0|
|w2_dense_cn|CAPRA|176|{'F': 102, 'R': 13, 'K': 61}|14|49|37|62|0|0|
|w2_dense_cm|SIA-P|182|{'P': 182}|0|0|249|0|73|0|
|w2_dense_cm|CAPRA-Fixed|176|{'F': 176}|0|0|168|105|64|64|
|w2_dense_cm|CAPRA|178|{'F': 104, 'R': 16, 'K': 58}|13|51|58|85|56|56|

F/K/R可行次数、失败原因、Phi和未扣恢复sum-rho相对F分布、实际迁移和恢复见opportunity_summary.json及逐轮candidate_deltas.csv。R“仅成本优势”严格指Phi高于F但sum-rho不高于F，不代表全程JCT因果。

异敏感度共同入选→同类型→两任务GPU和可单节点容纳→F已同机/锁/直接迁移容量阻断的嵌套描述统计，见funnel_rounds及funnel_training_fraction。训练权重是出现该标志轮次内所有实际任务训练秒；并非成对机会独占训练时间，不同标志不可相加。直接迁移诊断固定第三方任务，不穷尽交换布局。

## 静态机制证书和动态漏点

静态4C+2M+2N证书为24CPU/499.98GB，rho=1.53/2.4/1。静态4C+4M候选中无416.68GB点，保留M250GB/rho1；合法连续416.68GB可得1.50004。这两者与动态结果分开，详见development/static_certificates.json。

动态证书固定其他任务、GPU计划及位置，只使用决策时已有空闲资源，且标记恢复锁。每个证书独立成立；多个证书可能争用相同空闲资源，禁止累计预测增益。RAM漏点还要求在当前冻结候选RAM集合中没有能用该闲置RAM产生正增益的点。完整证书见每格analysis_r1/slack_certificates.json。

## CN/CM SIA-P严格控制

控制结果：**PASS**。工作负载/集群哈希、共同费用、逐作业完成/等待/训练/恢复/进度，以及逐轮GPU计划、分配、batch、恢复状态与执行分段全部比较；排除墙钟、缓存、路径与场景名。详情cn_cm_siap_control.json。

## 复现、冻结及边界

冻结1035文件；算法及上游保护1002文件，历史与输入保护1209文件。源码包frozen_source.zip可直接复原。27项测试、两次20作业/60轮pilot、真实孙进程Job Object清理、原六格复制重放及相对路径重放通过；pilot未完成全体JCT为空，不参与主表。

准备测试开始到矩阵结束的单调时钟用时78.61/120分钟；包含准备运行、复核、写盘、进程清理及中间开发等待。格wall总计74.35分钟，不能把它替代总预算。分析和报告在正式实验后单独进行，不启动新模拟。

单格900秒runner/960秒所属进程树/6000轮，Windows Job Object在挂起创建后分配、恢复执行，终止后确认后代为0；不按进程名终止其他项目。每格记录process/termination和原始输入哈希；无参数搜索、无选择性删除正负结果、无现场算法调参。

在新工作副本根目录运行（输出目录必须不存在）：

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts/build_scenarios_r1.py --check
.\.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -X utf8 -B -m capra.runner_v2 --input data/scenarios_r1/w2_dense.csv --cluster data/scenarios_r1/cluster_cpu3.json --responses data/scenarios_r1/responses_cm.json --scenario-id w2_dense_cm --run-version CAPRA_V2_SCENARIOS_R1_REPRO --method CAPRA --output runs/scenarios_r1/reproduce-new/CAPRA --max-rounds 6000 --wall-limit 900
.\.venv\Scripts\python.exe -X utf8 -B -c "from capra.audit_v2 import audit; print(audit('runs/scenarios_r1/reproduce-new/CAPRA'))"
.\.venv\Scripts\python.exe -X utf8 -B scripts/analyze_scenarios_r1.py
.\.venv\Scripts\python.exe -X utf8 -B scripts/report_scenarios_r1.py
```

本轮18格由run_scenarios_r1.py在冻结后一次执行，已有results时拒绝覆写/静默续跑。新机器重现实验须恢复源代码包和锁定环境、独立新目录、重新登记预算及冻结，不复用已耗尽的单调时钟截止。输入生成器可不带--check生成，所有已有目标必须字节相同，否则全部拒绝写入。

可解释范围：合成CPU/RAM响应和两条原GPU负载的受控仿真，不是实机测量，不是跨大量负载普遍验证。原画像→CN改变多项响应；只有CN→CM是严格RAM单因素对照。有限候选和F/K/R不保证全局rho或JCT最优，尚未区分全部可能布局/配额oracle差距。

## 逐项研究结论与剩余问题

### 1. 到达密度：更拥挤没有增强辅助配额加速

W2的CAPRA训练加权rho由原场景1.1500降到密集场景1.0513，超过比例性能的训练份额由15.36%降到7.56%。所以本轮密度变化没有增加实际利用的配额加速。该比较受动态GPU轨迹及任务时间份额共同影响，不能单独估计物理机会总量。
W6的CAPRA训练加权rho由原场景1.2127降到密集场景1.0973，超过比例性能的训练份额由23.98%降到15.86%。所以本轮密度变化没有增加实际利用的配额加速。该比较受动态GPU轨迹及任务时间份额共同影响，不能单独估计物理机会总量。

密集场景CAPRA仍比同场景SIA-P/Fixed更快，需同时看恢复和训练时间。互补任务共同入选、同GPU类型和可装入同节点是不同条件；原画像的DS在比例点已饱和、BERT训练份额小。不能用“多数CIFAR单任务占满节点”解释本结果，也不能由同机闲置资源证书为零推断所有布局已最优。

### 2. CPU2/3/6：容量本身与重分配分开

CPU2：SIA-P mean=2801.55，CAPRA mean=2359.53，同场景改善15.78%；CAPRA加权rho=0.7250，加权rho/rho_prop=1.0343，超比例训练份额=4.66%。
CPU3：SIA-P mean=1774.46，CAPRA mean=1462.99，同场景改善17.55%；CAPRA加权rho=1.0513，加权rho/rho_prop=1.0513，超比例训练份额=7.56%。
CPU6：SIA-P mean=1028.35，CAPRA mean=905.65，同场景改善11.93%；CAPRA加权rho=1.4024，加权rho/rho_prop=1.0610，超比例训练份额=17.28%。

CPU6更快的基线首先反映容量本身；其rho不能直接与CPU2的rho比较后宣称调度收益。CPU6/Fixed mean=1037.025，比同场景SIA-P的1028.35慢约0.84%，表明瞬时比例性能保底不等于动态JCT保证。该负结果保持原样，没有重跑。

### 3. CN：持续CPU供给确实增加，F已覆盖相当一部分同机组合

CAPRA实际低于比例CPU且不损比例rho的训练份额由原密集场景2.50%增到CN的42.77%；加权rho由1.0513增到1.0837，超过比例训练份额由7.56%增到10.78%。这证明CPU捐出更持续且部分转化为实际加速，但转换幅度远小于捐出训练份额增幅。
CN/CAPRA中，115个非空轮次存在同GPU类型且两任务GPU和可装入节点的CPU互补对；其中107轮F已至少同机放置一对，25轮全部可组合的异类任务对已经在F同机。另有78轮出现固定其他任务时直接迁移被目标节点GPU容量阻止的任务对。这些条件重叠，不能相加，也不表示全部机会被F用尽。

CPU/RAM donor角色定义为：在本场景比例点，至少存在一个更低的合法既有轴点可以保持比例rho，另一资源固定比例。它是画像能力；实际捐出份额另由真实配额计算。原画像→CN同时改变DS、CIFAR与BERT辅助响应，不是严格CPU单因素消融。

### 4. CM：新增RAM响应是否被实际利用

CAPRA-Fixed：CM对CN平均JCT改善7.40%；实际RAM条件增益的训练时间加权均值=0.03397，正RAM增益训练份额=3.70%（CN均为0）。配额、画像和实际执行段共同支持“新增RAM机会被部分利用”，不是只看终局JCT。
CAPRA：CM对CN平均JCT改善1.58%；实际RAM条件增益的训练时间加权均值=0.02479，正RAM增益训练份额=3.54%（CN均为0）。配额、画像和实际执行段共同支持“新增RAM机会被部分利用”，不是只看终局JCT。

CN/CM只改变DS的RAM响应，且SIA-P完整语义轨迹控制通过；可以检验这项输入因素的动态影响。CPU分配、GPU轨迹、恢复及任务份额仍可能随RAM响应共同演化，因此不能把条件增益数值直接换算成JCT的独立CPU/RAM因果份额。

### 5. 自由放置相对Fixed：实际时间账本

下表为CAPRA减Fixed，负数表示该时间项减少；三个差值之和等于mean JCT差。这是两次完整动态运行的实际时间账本，不是固定GPU轨迹的因果消融。

|场景|Δ等待|Δ训练|Δ恢复|Δmean JCT|选择F/K/R|
|---|---:|---:|---:|---:|---|
|w2_dense_original|-18.00|-83.00|-130.31|-231.31|{'F': 97, 'R': 8, 'K': 70}|
|w6_dense_original|-2.25|-106.16|-93.50|-201.91|{'F': 132, 'R': 10, 'K': 52}|
|w2_dense_cpu2|-27.00|-81.65|-146.88|-255.53|{'F': 111, 'R': 2, 'K': 112}|
|w2_dense_cpu6|-3.75|-68.94|-58.69|-131.38|{'F': 133, 'K': 36, 'R': 4}|
|w2_dense_cn|-0.75|-65.84|-114.81|-181.40|{'F': 102, 'R': 13, 'K': 61}|
|w2_dense_cm|-3.00|-30.54|-52.75|-86.29|{'F': 104, 'R': 16, 'K': 58}|

每场景的R未扣恢复sum-rho增益与Phi增益另见sum_rho_minus_F、phi_minus_F；Phi高但sum-rho不高的R轮次，其同状态评分优势来自恢复延迟项。不能把这些预测节费相加当成最终JCT差，也不能把K/R选择次数当成训练加速次数。

### 6. RAM网格遗漏已经出现在动态正式轨迹

CM/CAPRA-Fixed：64个非空轮次有独立RAM漏点证书，涉及训练时间份额9.36%。这些证书固定其他任务与位置，并排除决策时恢复锁，不是静态例推断。
实例：round 90（t=5400），`deepspeech2-40`在`dgx-ext:1`用4GPU/4.00CPU/250.00GB，rho=1.00000，实际训练35.00秒。该节点当轮空闲RAM=166.68GB，保持CPU和其他任务不变，将目标RAM设为416.68GB可得rho=1.50004；冻结候选RAM池为[83.32, 250.0, 500]，无任何当前可容纳的正增益候选点。
CM/CAPRA：56个非空轮次有独立RAM漏点证书，涉及训练时间份额8.05%。这些证书固定其他任务与位置，并排除决策时恢复锁，不是静态例推断。
实例：round 72（t=4320），`deepspeech2-19`在`dgx-ext:1`用4GPU/4.00CPU/250.00GB，rho=1.00000，实际训练35.00秒。该节点当轮空闲RAM=166.68GB，保持CPU和其他任务不变，将目标RAM设为416.68GB可得rho=1.50004；冻结候选RAM池为[83.32, 250.0, 500]，无任何当前可容纳的正增益候选点。

这是本轮已经证实的配额候选局限，不是整个放置空间全局最优差距的证明。同类型GPU数量、恢复锁和固定其他任务的容量约束也可限制机会；完整筛选分布及各轮证书保留在原始分析文件。不同目标可能共享空闲资源，禁止把单证书增益相加。

### 7. 均值与尾部

w2_dense_original：CAPRA对SIA-P的P95改善4.39%、P99改善10.91%；正数更快，负数为尾部退化。
w6_dense_original：CAPRA对SIA-P的P95改善11.07%、P99改善11.44%；正数更快，负数为尾部退化。
w2_dense_cpu2：CAPRA对SIA-P的P95改善10.14%、P99改善10.49%；正数更快，负数为尾部退化。
w2_dense_cpu6：CAPRA对SIA-P的P95改善-1.28%、P99改善9.58%；正数更快，负数为尾部退化。
w2_dense_cn：CAPRA对SIA-P的P95改善12.75%、P99改善12.74%；正数更快，负数为尾部退化。
w2_dense_cm：CAPRA对SIA-P的P95改善18.98%、P99改善12.59%；正数更快，负数为尾部退化。
本次CAPRA相对SIA-P存在尾部退化的场景：w2_dense_cpu6。这不撤销原v2 W2的尾部负结果，也不形成尾部性能保证。Fixed的负面结果及CAPRA对Fixed的各项尾部比较同样完整保留在comparisons.csv。

### 8. 可信结论与下一版最小方向

本轮支持：节点内重分配确实产生CPU及RAM训练增益；自由放置相对Fixed的增量需要同时核对训练和恢复，不能等同于纯资源吞吐收益；更多CPU或更密到达不必然扩大资源优化空间。F在许多实际可组合轮次已经同机放置至少一对互补任务，而恢复成本和同型GPU装箱限制仍然存在。

本轮不能确定：三布局之外是否存在显著更优布局、当前GPU计划是否遗漏更大跨类型联合机会、每个启发式距离全局JCT最优多远。未运行oracle或新消融，不能自行宣称F/R已全局充分利用，也不能将剩余问题全归咎于测试数据。

下一版最小且有证据的方向，是单独修复已证实的RAM剩余容量候选漏点，保持有限搜索边界，再另行登记同输入对照验证；本轮没有执行该修改、没有重调H、没有追加实验。合成敏感度的说服力仍限于受控仿真机制验证，真实画像与更广负载验证是后续独立问题。
