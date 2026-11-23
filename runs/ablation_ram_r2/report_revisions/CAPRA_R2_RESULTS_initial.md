# CAPRA R2：机制消融与RAM剩余容量修复结果

唯一基准 `81b1109ab1124feeac4e846003f4383b39143fc4`；分支 `capra/ablation-ram-r2`；工作副本 `D:/科研启航/CAPRA-ablation-ram-r2`。正式完成9/9格，新增作业完成720/720。旧R1的18格/1440次执行为历史，其中本轮分析只读复用三个场景的9格/720次，绝不计为新增样本。

本轮先实现并同时冻结A/B，再顺序运行A六格和B三格。关闭修复时旧方法语义由54个固定状态回放证明；原33项测试通过，全部288条旧RAM证书按完整实际节点分为151组，顺序修复后终局无合法正增益。仅两次12作业30轮冒烟（未完成整体JCT为空），内部18次测试Job.step也有登记。

## 来源与公平边界

旧SIA-P/Fixed/完整CAPRA来自提交81b1109中的CAPRA_V2_SCENARIOS_R1；A新增SIA-P-K和FK用原比例/legacy分配；B的Fixed/FK/CAPRA同用ram_slack_v1。B前后FK旧值来自A第6格，其余旧值来自R1。SIA-P与SIA-P-K未在B重跑。source_index.json/csv记录每格来源、版本、路径、哈希和新/复用身份。

GPU阶段、上游、execution、identity、costs、response、node_allocator、旧placement/runner/audit、输入与历史全部原字节保护。新入口为runner_r2/placement_r2/audit_r2/audit_ram_r2，RAM仅包装原节点最终解。输入/40GPU/6节点/恢复费/H180/60秒周期/seed0/数值线程1不变，neutral=false。Python3.10.10、NumPy1.26.4、SciPy1.13.1、CVXPY1.6.5，HiGHS包装器二进制与R1环境哈希相同。

改善率=100×(1−method/baseline)，正为更快。两次动态运行时间差只称时间账本，不是严格组件因果。相对基线JCT比值不是相对于独占时间的经典slowdown。单个固定种子和派生场景不构成独立随机重复，不制造显著性。

## A：三个场景五方法

|场景|方法|来源|完成/状态|mean|P50|P95|P99|makespan|
|---|---|---|---|---:|---:|---:|---:|---:|
|w2_dense_original|SIA-P|R1复用|80/80 ALL_COMPLETE|1774.46|1558.00|5257.32|6062.61|10895.00|
|w2_dense_original|CAPRA-Fixed|R1复用|80/80 ALL_COMPLETE|1694.30|1531.50|5210.82|6139.34|10948.00|
|w2_dense_original|SIA-P-K|A新增|80/80 ALL_COMPLETE|1503.03|1156.00|5174.52|5872.26|10760.00|
|w2_dense_original|CAPRA-FK|A新增|80/80 ALL_COMPLETE|1507.99|1289.25|4863.18|5571.44|10584.00|
|w2_dense_original|CAPRA|R1复用|80/80 ALL_COMPLETE|1462.99|1168.50|5026.30|5400.93|10510.00|
|w6_dense_original|SIA-P|R1复用|80/80 ALL_COMPLETE|1487.47|1184.25|3613.57|5096.30|11740.00|
|w6_dense_original|CAPRA-Fixed|R1复用|80/80 ALL_COMPLETE|1372.79|1017.00|3368.05|4924.84|11648.00|
|w6_dense_original|SIA-P-K|A新增|80/80 ALL_COMPLETE|1258.82|876.00|3153.90|4617.23|11719.00|
|w6_dense_original|CAPRA-FK|A新增|80/80 ALL_COMPLETE|1182.87|815.25|3244.37|4577.16|11620.00|
|w6_dense_original|CAPRA|R1复用|80/80 ALL_COMPLETE|1170.88|802.75|3213.37|4513.17|11636.00|
|w2_dense_cm|SIA-P|R1复用|80/80 ALL_COMPLETE|1774.46|1558.00|5257.32|6062.61|10895.00|
|w2_dense_cm|CAPRA-Fixed|R1复用|80/80 ALL_COMPLETE|1467.22|1176.00|4544.67|5382.48|10569.00|
|w2_dense_cm|SIA-P-K|A新增|80/80 ALL_COMPLETE|1503.03|1156.00|5174.52|5872.26|10760.00|
|w2_dense_cm|CAPRA-FK|A新增|80/80 ALL_COMPLETE|1373.30|1128.00|4256.05|5028.48|10572.00|
|w2_dense_cm|CAPRA|R1复用|80/80 ALL_COMPLETE|1380.94|1125.50|4259.22|5299.56|10650.00|

|场景|仅位置 P-K/P|优化下位置 FK/Fixed|对齐位置资源 FK/P-K|R增量 FKR/FK|
|---|---:|---:|---:|---:|
|w2_dense_original|15.30%|11.00%|-0.33%|2.98%|
|w6_dense_original|15.37%|13.83%|6.03%|1.01%|
|w2_dense_cm|15.30%|6.40%|8.63%|-0.56%|

![A五方法](../runs/ablation_ram_r2/figures/A_five_methods.png)

## B：CM三方法RAM修复前后

|方法|分配器|来源|完成|mean|P95|P99|等待|训练|恢复|
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
|CAPRA-Fixed|legacy|R1|80|1467.22|4544.67|5382.48|43.27|1149.08|274.88|
|CAPRA-Fixed|ram_slack_v1|B|80|1507.79|4604.52|5301.38|42.52|1155.51|309.75|
|CAPRA-FK|legacy|A|80|1373.30|4256.05|5028.48|42.52|1113.46|217.31|
|CAPRA-FK|ram_slack_v1|B|80|1340.78|4233.40|4936.14|39.52|1085.81|215.44|
|CAPRA|legacy|R1|80|1380.94|4259.22|5299.56|40.27|1118.54|222.12|
|CAPRA|ram_slack_v1|B|80|1217.35|3603.17|4368.63|42.52|967.26|207.56|

修复前后及同修复版本的比较见comparisons.csv/json；不将修复后的CAPRA对未修复Fixed当作公平方法增量。背景比例方法沿用A/R1并明确未在B执行。

![CM RAM修复前后](../runs/ablation_ram_r2/figures/CM_ram_before_after.png)

## 全部预定比较与逐作业退化

|阶段/场景|比较|mean改善%|P95改善%|P99改善%|快/平/慢|比值P95/max|最大比值作业|
|---|---|---:|---:|---:|---|---|---|
|A/w2_dense_original|SIA-P-K/SIA-P|15.30|1.57|3.14|57/9/14|1.098/1.278|cifar10-36|
|A/w2_dense_original|CAPRA-FK/CAPRA-Fixed|11.00|6.67|9.25|58/12/10|1.105/1.346|cifar10-37|
|A/w2_dense_original|CAPRA-FK/SIA-P-K|-0.33|6.02|5.12|35/2/43|1.228/1.808|cifar10-100|
|A/w2_dense_original|CAPRA/CAPRA-FK|2.98|-3.35|3.06|43/15/22|1.098/1.236|cifar10-35|
|A/w2_dense_original|CAPRA/SIA-P|17.55|4.39|10.91|70/0/10|1.068/1.217|cifar10-63|
|A/w2_dense_original|CAPRA/CAPRA-Fixed|13.65|3.54|12.03|60/9/11|1.054/1.120|deepspeech2-40|
|A/w6_dense_original|SIA-P-K/SIA-P|15.37|12.72|9.40|56/9/15|1.091/1.273|cifar10-77|
|A/w6_dense_original|CAPRA-FK/CAPRA-Fixed|13.83|3.67|7.06|57/7/16|1.170/1.855|cifar10-36|
|A/w6_dense_original|CAPRA-FK/SIA-P-K|6.03|-2.87|0.87|57/0/23|1.175/1.303|cifar10-65|
|A/w6_dense_original|CAPRA/CAPRA-FK|1.01|0.96|1.40|21/43/16|1.075/1.205|cifar10-106|
|A/w6_dense_original|CAPRA/SIA-P|21.28|11.07|11.44|74/0/6|1.056/1.282|cifar10-36|
|A/w6_dense_original|CAPRA/CAPRA-Fixed|14.71|4.59|8.36|58/7/15|1.181/1.855|cifar10-36|
|A/w2_dense_cm|SIA-P-K/SIA-P|15.30|1.57|3.14|57/9/14|1.098/1.278|cifar10-36|
|A/w2_dense_cm|CAPRA-FK/CAPRA-Fixed|6.40|6.35|6.58|47/9/24|1.158/1.256|cifar10-100|
|A/w2_dense_cm|CAPRA-FK/SIA-P-K|8.63|17.75|14.37|55/0/25|1.159/1.695|cifar10-100|
|A/w2_dense_cm|CAPRA/CAPRA-FK|-0.56|-0.07|-5.39|37/8/35|1.262/1.696|cifar10-76|
|A/w2_dense_cm|CAPRA/SIA-P|22.18|18.98|12.59|73/0/7|1.028/1.095|cifar10-68|
|A/w2_dense_cm|CAPRA/CAPRA-Fixed|5.88|6.28|1.54|50/8/22|1.179/1.461|cifar10-140|
|B/w2_dense_cm|CAPRA-Fixed_repaired/CAPRA-Fixed_legacy|-2.76|-1.32|1.51|19/31/30|1.340/1.428|cifar10-112|
|B/w2_dense_cm|CAPRA-FK_repaired/CAPRA-FK_legacy|2.37|0.53|1.84|32/24/24|1.172/1.682|cifar10-76|
|B/w2_dense_cm|CAPRA_repaired/CAPRA_legacy|11.85|15.40|17.57|45/22/13|1.124/1.387|cifar10-73|
|B/w2_dense_cm|CAPRA-FK/CAPRA-Fixed|11.08|8.06|6.89|54/9/17|1.114/1.346|cifar10-106|
|B/w2_dense_cm|CAPRA/CAPRA-FK|9.21|14.89|11.50|51/10/19|1.119/1.703|cifar10-96|
|B/w2_dense_cm|CAPRA/CAPRA-Fixed|19.26|21.75|17.59|63/8/9|1.055/1.144|cifar10-141|

全体逐作业正负差异见paired_jobs.csv；worst_cases.json同时保留最大比值和最大绝对JCT退化的任务及等待/训练/恢复。比值分母为该基线方法同任务JCT，不能称经典独占slowdown。

## 实际时间账本分解

|阶段/场景|比较|Δ等待|Δ训练|Δ恢复|三项合计|
|---|---|---:|---:|---:|---:|
|A/w2_dense_original|SIA-P-K/SIA-P|-29.25|-114.81|-127.38|-271.44|
|A/w2_dense_original|CAPRA-FK/CAPRA-Fixed|-15.00|-70.44|-100.88|-186.31|
|A/w2_dense_original|CAPRA-FK/SIA-P-K|0.75|-7.72|11.94|4.96|
|A/w2_dense_original|CAPRA/CAPRA-FK|-3.00|-12.56|-29.44|-45.00|
|A/w2_dense_original|CAPRA/SIA-P|-31.50|-135.10|-144.88|-311.47|
|A/w2_dense_original|CAPRA/CAPRA-Fixed|-18.00|-83.00|-130.31|-231.31|
|A/w6_dense_original|SIA-P-K/SIA-P|-1.50|-97.15|-130.00|-228.65|
|A/w6_dense_original|CAPRA-FK/CAPRA-Fixed|1.50|-111.43|-80.00|-189.93|
|A/w6_dense_original|CAPRA-FK/SIA-P-K|2.25|-92.89|14.69|-75.95|
|A/w6_dense_original|CAPRA/CAPRA-FK|-3.75|5.26|-13.50|-11.99|
|A/w6_dense_original|CAPRA/SIA-P|-3.00|-184.77|-128.81|-316.59|
|A/w6_dense_original|CAPRA/CAPRA-Fixed|-2.25|-106.16|-93.50|-201.91|
|A/w2_dense_cm|SIA-P-K/SIA-P|-29.25|-114.81|-127.38|-271.44|
|A/w2_dense_cm|CAPRA-FK/CAPRA-Fixed|-0.75|-35.61|-57.56|-93.92|
|A/w2_dense_cm|CAPRA-FK/SIA-P-K|2.25|-140.54|8.56|-129.72|
|A/w2_dense_cm|CAPRA/CAPRA-FK|-2.25|5.07|4.81|7.64|
|A/w2_dense_cm|CAPRA/SIA-P|-29.25|-250.28|-114.00|-393.53|
|A/w2_dense_cm|CAPRA/CAPRA-Fixed|-3.00|-30.54|-52.75|-86.29|
|B/w2_dense_cm|CAPRA-Fixed_repaired/CAPRA-Fixed_legacy|-0.75|6.44|34.88|40.56|
|B/w2_dense_cm|CAPRA-FK_repaired/CAPRA-FK_legacy|-3.00|-27.65|-1.88|-32.53|
|B/w2_dense_cm|CAPRA_repaired/CAPRA_legacy|2.25|-151.27|-14.56|-163.59|
|B/w2_dense_cm|CAPRA-FK/CAPRA-Fixed|-3.00|-69.70|-94.31|-167.01|
|B/w2_dense_cm|CAPRA/CAPRA-FK|3.00|-118.55|-7.88|-123.42|
|B/w2_dense_cm|CAPRA/CAPRA-Fixed|0.00|-188.25|-102.19|-290.44|

## 每应用结果

|来源/场景/方法|应用|作业数|平均JCT|
|---|---|---:|---:|
|R1/w2_dense_original/SIA-P|bert|3|1762.67|
|R1/w2_dense_original/SIA-P|cifar10|68|1329.57|
|R1/w2_dense_original/SIA-P|deepspeech2|9|5139.83|
|R1/w2_dense_original/CAPRA-Fixed|bert|3|1631.67|
|R1/w2_dense_original/CAPRA-Fixed|cifar10|68|1268.74|
|R1/w2_dense_original/CAPRA-Fixed|deepspeech2|9|4930.50|
|R1/w2_dense_original/CAPRA|bert|3|1272.67|
|R1/w2_dense_original/CAPRA|cifar10|68|1046.52|
|R1/w2_dense_original/CAPRA|deepspeech2|9|4673.06|
|R1/w6_dense_original/SIA-P|bert|5|1533.10|
|R1/w6_dense_original/SIA-P|cifar10|67|1188.19|
|R1/w6_dense_original/SIA-P|deepspeech2|8|3965.38|
|R1/w6_dense_original/CAPRA-Fixed|bert|5|1544.70|
|R1/w6_dense_original/CAPRA-Fixed|cifar10|67|1064.85|
|R1/w6_dense_original/CAPRA-Fixed|deepspeech2|8|3844.38|
|R1/w6_dense_original/CAPRA|bert|5|1364.70|
|R1/w6_dense_original/CAPRA|cifar10|67|852.30|
|R1/w6_dense_original/CAPRA|deepspeech2|8|3717.88|
|R1/w2_dense_cm/SIA-P|bert|3|1762.67|
|R1/w2_dense_cm/SIA-P|cifar10|68|1329.57|
|R1/w2_dense_cm/SIA-P|deepspeech2|9|5139.83|
|R1/w2_dense_cm/CAPRA-Fixed|bert|3|1400.00|
|R1/w2_dense_cm/CAPRA-Fixed|cifar10|68|1087.14|
|R1/w2_dense_cm/CAPRA-Fixed|deepspeech2|9|4361.39|
|R1/w2_dense_cm/CAPRA|bert|3|1376.67|
|R1/w2_dense_cm/CAPRA|cifar10|68|1011.02|
|R1/w2_dense_cm/CAPRA|deepspeech2|9|4177.28|
|A/w2_dense_original/SIA-P-K|bert|3|1358.00|
|A/w2_dense_original/SIA-P-K|cifar10|68|1080.88|
|A/w2_dense_original/SIA-P-K|deepspeech2|9|4740.94|
|A/w2_dense_original/CAPRA-FK|bert|3|1475.00|
|A/w2_dense_original/CAPRA-FK|cifar10|68|1098.02|
|A/w2_dense_original/CAPRA-FK|deepspeech2|9|4616.50|
|A/w6_dense_original/SIA-P-K|bert|5|1420.30|
|A/w6_dense_original/SIA-P-K|cifar10|67|958.84|
|A/w6_dense_original/SIA-P-K|deepspeech2|8|3670.25|
|A/w6_dense_original/CAPRA-FK|bert|5|1417.10|
|A/w6_dense_original/CAPRA-FK|cifar10|67|860.72|
|A/w6_dense_original/CAPRA-FK|deepspeech2|8|3734.50|
|A/w2_dense_cm/SIA-P-K|bert|3|1358.00|
|A/w2_dense_cm/SIA-P-K|cifar10|68|1080.88|
|A/w2_dense_cm/SIA-P-K|deepspeech2|9|4740.94|
|A/w2_dense_cm/CAPRA-FK|bert|3|1381.67|
|A/w2_dense_cm/CAPRA-FK|cifar10|68|1011.45|
|A/w2_dense_cm/CAPRA-FK|deepspeech2|9|4104.50|
|B/w2_dense_cm/CAPRA-Fixed|bert|3|1470.33|
|B/w2_dense_cm/CAPRA-Fixed|cifar10|68|1130.15|
|B/w2_dense_cm/CAPRA-Fixed|deepspeech2|9|4373.50|
|B/w2_dense_cm/CAPRA-FK|bert|3|1396.33|
|B/w2_dense_cm/CAPRA-FK|cifar10|68|984.73|
|B/w2_dense_cm/CAPRA-FK|deepspeech2|9|4012.39|
|B/w2_dense_cm/CAPRA|bert|3|1329.67|
|B/w2_dense_cm/CAPRA|cifar10|68|892.18|
|B/w2_dense_cm/CAPRA|deepspeech2|9|3636.72|

## 响应与RAM实际执行指标

全部由实际训练段加权。rho_prop按本节点比例CPU/RAM计算；CPU条件差=rho(c,m)−rho(c_prop,m)，RAM条件差=rho(c,m)−rho(c,m_prop)，两者不能相加解释总收益或换算JCT。

|来源/场景/方法|rho|rho/rho_prop|超比例训练%|CPU条件差|CPU正训练%|RAM条件差|RAM正训练%|
|---|---:|---:|---:|---:|---:|---:|---:|
|R1/w2_dense_original/SIA-P|1.0000|1.0000|0.00|0.00000|0.00|0.00000|0.00|
|R1/w2_dense_original/CAPRA-Fixed|1.0460|1.0460|7.27|0.04599|7.27|0.00000|0.00|
|R1/w2_dense_original/CAPRA|1.0513|1.0513|7.56|0.05131|7.56|0.00000|0.00|
|R1/w6_dense_original/SIA-P|1.0000|1.0000|0.00|0.00000|0.00|0.00000|0.00|
|R1/w6_dense_original/CAPRA-Fixed|1.0770|1.0770|14.22|0.07696|14.22|0.00000|0.00|
|R1/w6_dense_original/CAPRA|1.0973|1.0973|15.86|0.09734|15.86|0.00000|0.00|
|R1/w2_dense_cm/SIA-P|1.0000|1.0000|0.00|0.00000|0.00|0.00000|0.00|
|R1/w2_dense_cm/CAPRA-Fixed|1.1396|1.1396|18.63|0.10559|14.92|0.03397|3.70|
|R1/w2_dense_cm/CAPRA|1.1171|1.1171|15.47|0.09229|11.93|0.02479|3.54|
|A/w2_dense_original/SIA-P-K|1.0000|1.0000|0.00|0.00000|0.00|0.00000|0.00|
|A/w2_dense_original/CAPRA-FK|1.0507|1.0507|7.75|0.05074|7.75|0.00000|0.00|
|A/w6_dense_original/SIA-P-K|1.0000|1.0000|0.00|0.00000|0.00|0.00000|0.00|
|A/w6_dense_original/CAPRA-FK|1.0969|1.0969|15.16|0.09688|15.16|0.00000|0.00|
|A/w2_dense_cm/SIA-P-K|1.0000|1.0000|0.00|0.00000|0.00|0.00000|0.00|
|A/w2_dense_cm/CAPRA-FK|1.1204|1.1204|16.86|0.08512|12.93|0.03527|3.92|
|B/w2_dense_cm/CAPRA-Fixed|1.1492|1.1492|22.06|0.09940|14.40|0.04980|7.65|
|B/w2_dense_cm/CAPRA-FK|1.1466|1.1466|21.50|0.09908|14.70|0.04752|6.80|
|B/w2_dense_cm/CAPRA|1.2692|1.2692|39.90|0.16451|26.03|0.10467|13.87|

|修复版方法|全部试算RAM调用/步骤/候选|最终选中更新|本轮补充影响训练%|非轴RAM训练%|训练加权额外GB|剩余机会轮|
|---|---|---:|---:|---:|---:|---:|
|CAPRA-Fixed|774/27/4460|27|1.21|4.04|0.75|0|
|CAPRA-FK|936/41/6344|27|1.43|3.92|1.33|0|
|CAPRA|3862/171/19886|30|1.85|6.86|1.63|0|

“本轮补充影响训练”只计算当轮选择候选中相对旧最终节点解额外加RAM的任务；当前向量可能保留前轮新增中间点，所以非轴RAM训练份额另列。额外GB是对同轮旧节点最终解的差，不是跨运行硬件使用差。全部试算包含未选择R部分布局，不当作实际训练。各步原始证据在selection.allocator.ram_traces；分析目录ram_training_points.csv记录实际配额。

终局机会直接检查固定CPU/位置、其他任务不变时的真实RAM上界，不使用旧pool_ram作为修复后的判据。残余证书逐个成立，不能累加共享空闲RAM的假想收益；旧288条验证分151组完整节点顺序执行，151次接受更新，无终局合法正增益。

## F/K/R、恢复与计时

|来源/场景/方法|非空轮|选择|可行|纯节点迁移|其他GPU配置变动|aux更新|实际恢复总秒|R调用|
|---|---:|---|---|---:|---:|---:|---:|---:|
|R1/w2_dense_original/SIA-P|182|{'P': 182}|{'P': 182}|249|249|0|26890.00|旧日志不可得|
|R1/w2_dense_original/CAPRA-Fixed|183|{'F': 183}|{'F': 183}|229|250|46|25725.00|旧日志不可得|
|R1/w2_dense_original/CAPRA|175|{'F': 97, 'R': 8, 'K': 70}|{'F': 175, 'K': 166, 'R': 175}|24|241|45|15300.00|旧日志不可得|
|R1/w6_dense_original/SIA-P|196|{'P': 196}|{'P': 196}|223|276|0|28215.00|旧日志不可得|
|R1/w6_dense_original/CAPRA-Fixed|194|{'F': 194}|{'F': 194}|201|240|55|25390.00|旧日志不可得|
|R1/w6_dense_original/CAPRA|194|{'F': 132, 'R': 10, 'K': 52}|{'F': 194, 'K': 180, 'R': 194}|39|248|55|17910.00|旧日志不可得|
|R1/w2_dense_cm/SIA-P|182|{'P': 182}|{'P': 182}|249|249|0|26890.00|旧日志不可得|
|R1/w2_dense_cm/CAPRA-Fixed|176|{'F': 176}|{'F': 176}|168|235|105|21990.00|旧日志不可得|
|R1/w2_dense_cm/CAPRA|178|{'F': 104, 'R': 16, 'K': 58}|{'F': 178, 'K': 162, 'R': 178}|58|241|85|17770.00|旧日志不可得|
|A/w2_dense_original/SIA-P-K|180|{'F': 95, 'K': 85}|{'F': 180, 'K': 167}|35|252|0|16700.00|0|
|A/w2_dense_original/CAPRA-FK|177|{'F': 118, 'K': 59}|{'F': 177, 'K': 161}|65|241|48|17655.00|0|
|A/w6_dense_original/SIA-P-K|195|{'F': 124, 'K': 71}|{'F': 195, 'K': 182}|23|261|0|17815.00|0|
|A/w6_dense_original/CAPRA-FK|194|{'F': 141, 'K': 53}|{'F': 194, 'K': 179}|47|258|50|18990.00|0|
|A/w2_dense_cm/SIA-P-K|180|{'F': 95, 'K': 85}|{'F': 180, 'K': 167}|35|252|0|16700.00|0|
|A/w2_dense_cm/CAPRA-FK|176|{'F': 116, 'K': 60}|{'F': 176, 'K': 163}|46|246|70|17385.00|0|
|B/w2_dense_cm/CAPRA-Fixed|176|{'F': 176}|{'F': 176}|216|242|114|24780.00|0|
|B/w2_dense_cm/CAPRA-FK|178|{'F': 125, 'K': 53}|{'F': 178, 'K': 168}|42|250|95|17235.00|0|
|B/w2_dense_cm/CAPRA|178|{'F': 99, 'R': 15, 'K': 64}|{'F': 178, 'K': 170, 'R': 178}|26|248|129|16605.00|178|

K不可行原因及Phi/未扣恢复sum-rho相对F分布在metrics.json和各格candidate_scores.csv。局部Phi与rho、K/R选择频次是机制描述，不直接换算动态贡献百分比。

|来源/场景/方法|完整决策median/P95/max|>5秒数/比例|格wall|F median/P95/max|K median/P95/max|R median/P95/max|RAM nested median/P95/max|
|---|---|---|---:|---|---|---|---|
|R1/w2_dense_original/SIA-P|0.0661/0.1699/0.3263|0/0.00%|190.45|不可得|不可得|不可得|不可得|
|R1/w2_dense_original/CAPRA-Fixed|0.0747/0.1902/0.2900|0/0.00%|180.65|不可得|不可得|不可得|不可得|
|R1/w2_dense_original/CAPRA|0.1168/3.2497/3.4523|0/0.00%|295.97|不可得|不可得|不可得|不可得|
|R1/w6_dense_original/SIA-P|0.0511/0.2272/0.3347|0/0.00%|241.64|不可得|不可得|不可得|不可得|
|R1/w6_dense_original/CAPRA-Fixed|0.0635/0.2563/0.4224|0/0.00%|236.36|不可得|不可得|不可得|不可得|
|R1/w6_dense_original/CAPRA|0.1040/2.3473/3.6162|0/0.00%|311.70|不可得|不可得|不可得|不可得|
|R1/w2_dense_cm/SIA-P|0.0649/0.1819/0.3278|0/0.00%|206.59|不可得|不可得|不可得|不可得|
|R1/w2_dense_cm/CAPRA-Fixed|0.0694/0.1936/0.3103|0/0.00%|198.80|不可得|不可得|不可得|不可得|
|R1/w2_dense_cm/CAPRA|0.1132/2.9560/3.8425|0/0.00%|322.74|不可得|不可得|不可得|不可得|
|A/w2_dense_original/SIA-P-K|0.0792/0.2113/0.3847|0/0.00%|253.21|0.0010/0.0033/0.0042|0.0019/0.0137/0.0282|不可得|0.0000/0.0000/0.0000|
|A/w2_dense_original/CAPRA-FK|0.0907/0.2847/0.4679|0/0.00%|234.91|0.0092/0.0472/0.0615|0.0026/0.0456/0.0852|不可得|0.0000/0.0000/0.0000|
|A/w6_dense_original/SIA-P-K|0.0627/0.1910/0.3357|0/0.00%|271.70|0.0009/0.0024/0.0044|0.0019/0.0110/0.0289|不可得|0.0000/0.0000/0.0000|
|A/w6_dense_original/CAPRA-FK|0.0707/0.2356/0.3367|0/0.00%|275.74|0.0081/0.0357/0.0521|0.0021/0.0374/0.0533|不可得|0.0000/0.0000/0.0000|
|A/w2_dense_cm/SIA-P-K|0.0756/0.2164/0.3964|0/0.00%|252.12|0.0010/0.0032/0.0039|0.0019/0.0146/0.0275|不可得|0.0000/0.0000/0.0000|
|A/w2_dense_cm/CAPRA-FK|0.0829/0.3094/0.4333|0/0.00%|256.49|0.0099/0.0548/0.0828|0.0030/0.0544/0.0953|不可得|0.0000/0.0000/0.0000|
|B/w2_dense_cm/CAPRA-Fixed|0.0908/0.2712/0.4683|0/0.00%|246.98|0.0130/0.0581/0.0800|不可得|不可得|0.0008/0.0026/0.0041|
|B/w2_dense_cm/CAPRA-FK|0.0870/0.2822/0.3905|0/0.00%|256.98|0.0111/0.0459/0.0671|0.0029/0.0486/0.0680|不可得|0.0008/0.0038/0.0055|
|B/w2_dense_cm/CAPRA|0.1184/3.0184/3.5540|0/0.00%|359.09|0.0104/0.0520/0.0813|0.0044/0.0482/0.1068|0.0377/2.7991/3.3050|0.0017/0.0157/0.0184|

主开销只用非空轮，all_rounds独立保留。F/K/R组件计时含对应配额、稳定和评分；RAM及mapping/scoring嵌套在候选耗时内，不能重复加总或机械相减。R1缺失的组件计时均标不可得，不估造或补跑；同机不同批次wall为描述性观测，B完整CAPRA提供修复版R的实际组件时间。完整GPU准备/MIP→参考→候选→验证→提交的decision边界保持不变，不预设严格5秒上限。

![R增量与开销](../runs/ablation_ram_r2/figures/R_increment_overhead.png)

## 版本、预算及实际调用

源码快照SHA256 `2dc99586fe53094fcb733b0f649eeabe4395563f5c59615f7123b172fe139e13`；A/B两份独立manifest SHA见freeze_receipt.json。源码包不包含manifest，manifest指源码包，start指manifest，避免自引用。冻结1037个文件；保护基准全部1713个跟踪文件。

共享实验预算46.26/90分钟，起点为首次准备验证前，包含测试、回放、两次冒烟、环境失败、修正重验、冻结、A/B九格、逐格审计写盘及进程清理。阶段不重置，无正式自动重试。初步阅读/开发和矩阵后纯离线分析报告另记于最终delivery_clock。

准备期曾因Python继承的Git命令配置COUNT缺少VALUE导致两次只读基准读取失败，未进入测试/模拟；保留preparation_01/02日志并仅修正该只读Git子进程的环境，未改全局Git配置。两次失败都在相同截止内。正式失败/未运行如有，完整保留root results和matrix_receipt，不将部分完成写成9/9。

全部模拟调用索引将在simulation_calls.json汇总：原单元测试18次Job.step、两次短冒烟、至多9个正式进程，各有预算和所属树清理回执。使用挂起创建→分配Windows Job Object→恢复执行→清理全后代机制，只操作本轮自有进程。原18格只读，不运行旧准备/分析/封存入口。

## 研究判断

详见最终研究判断附件。

## 复现与交付入口

在本工作副本根目录，使用锁定环境（输出目录须为不存在的新目录）：

```powershell
.\.venv\Scripts\python.exe -X utf8 -B -m capra.runner_r2 --input data/scenarios_r1/w2_dense.csv --cluster data/scenarios_r1/cluster_cpu3.json --responses data/scenarios_r1/responses_cm.json --scenario-id w2_dense_cm --run-version CAPRA_V2_RAM_R2_REPRO --allocator-mode ram_slack_v1 --method CAPRA-FK --output runs/ablation_ram_r2/reproduction-new/CAPRA-FK --max-rounds 6000 --wall-limit 900
.\.venv\Scripts\python.exe -X utf8 -B -c "from capra.audit_r2 import audit; print(audit('runs/ablation_ram_r2/reproduction-new/CAPRA-FK'))"
.\.venv\Scripts\python.exe -X utf8 -B scripts/analyze_r2.py
.\.venv\Scripts\python.exe -X utf8 -B scripts/report_r2.py
```

新复现若需正式冻结身份，必须新目录、新预算与新manifest；上述REPRO是非正式单格接口演示，不能重用原已消耗的单调时钟截止。原九格由run_r2.py一次顺序执行，已有results时拒绝覆写。

后续只读Saturn7/8来源核查与计划在docs/NEXT_VALIDATION_PLAN.md；本轮不生成该派生负载、不执行新矩阵。最终代码diff、证据hash、环境、调用索引和完整性核对在R2根目录/analysis。没有自动删除R或推送远端。
