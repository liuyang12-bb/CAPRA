# CAPRA v2 结果与交付

项目：`D:\科研启航\CAPRA`；分支`capra/v2-20261122`；冻结版本`CAPRA_V2_R1`，运行代码提交`2517e5cd6bfd93f094b728e226478d4cf56cc45f`。本轮没有远端推送；v1的99个保护文件、原两条80作业CSV、集群和响应表最终哈希保持一致。

22项原有/新增测试最终通过。新增跨设备fixture曾缺少AWS性能字典，修正fixture后通过；保留失败日志`development/tests_final.log`与通过日志`tests_final_02.log`，没有因此重跑正式格。12作业/80轮pilot37秒、原始审计通过，未完成整体JCT留空；仅用于正确性/耗时检查，不加入主表。

## v2 同版本主表

JCT与分位数单位为模拟秒。完整80/80才报告整体统计；负变化表示更快。H=180仅评分，周期仍60秒；控制器wall不扣模拟JCT，真实恢复照常收费。

| 负载 | 方法 | 完成/状态 | mean | 相对SIA-P-v2 | P50 | P95 | P99 | makespan |
|---|---|---|---:|---:|---:|---:|---:|---:|
| saturn-2-supported80 | SIA-P-v2 | 80/80 ALL_COMPLETE | 1056.11 | 0.00% | 763.50 | 3088.15 | 3800.98 | 20606.00 |
| saturn-2-supported80 | CAPRA-Fixed-v2 | 80/80 ALL_COMPLETE | 971.02 | -8.06% | 676.50 | 2990.45 | 3759.56 | 20479.00 |
| saturn-2-supported80 | CAPRA-v2 | 80/80 ALL_COMPLETE | 949.46 | -10.10% | 663.50 | 3264.05 | 4157.23 | 20444.00 |
| saturn-6-supported80 | SIA-P-v2 | 80/80 ALL_COMPLETE | 1056.55 | 0.00% | 736.50 | 2794.10 | 3298.29 | 22839.00 |
| saturn-6-supported80 | CAPRA-Fixed-v2 | 80/80 ALL_COMPLETE | 973.73 | -7.84% | 609.00 | 2777.55 | 3652.58 | 22590.00 |
| saturn-6-supported80 | CAPRA-v2 | 80/80 ALL_COMPLETE | 911.48 | -13.73% | 635.00 | 2804.15 | 3296.77 | 22593.00 |

- saturn-2-supported80：CAPRA-v2相对SIA-P-v2平均JCT变化-10.10%，相对Fixed-v2变化-2.22%；Fixed-v2相对SIA-P-v2变化-8.06%。
- saturn-6-supported80：CAPRA-v2相对SIA-P-v2平均JCT变化-13.73%，相对Fixed-v2变化-6.39%；Fixed-v2相对SIA-P-v2变化-7.84%。

## 时间分解与完整开销

| 负载 | 方法 | 等待 | 训练 | 恢复 | 决策中位/秒 | P95/秒 | max/秒 | 整格wall/秒 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| saturn-2-supported80 | SIA-P | 30.80 | 791.06 | 234.25 | 0.0304 | 0.0892 | 0.1583 | 222.73 |
| saturn-2-supported80 | CAPRA-Fixed | 31.55 | 723.04 | 216.44 | 0.0333 | 0.0992 | 0.1408 | 219.35 |
| saturn-2-supported80 | CAPRA | 31.55 | 729.85 | 188.06 | 0.0405 | 0.3153 | 0.5803 | 232.49 |
| saturn-6-supported80 | SIA-P | 29.69 | 772.74 | 254.12 | 0.0291 | 0.0963 | 0.2194 | 226.82 |
| saturn-6-supported80 | CAPRA-Fixed | 29.69 | 683.85 | 260.19 | 0.0299 | 0.1103 | 0.2249 | 228.94 |
| saturn-6-supported80 | CAPRA | 28.19 | 671.10 | 212.19 | 0.0352 | 0.3661 | 0.6321 | 236.07 |

平均节点GPU/CPU/RAM配额见`average_node_allocations.csv`；各格summary包含集群分配占比和节点均值，含恢复占用，不等于硬件忙碌率。各应用训练时间占比见`supplementary_metrics.json`。完整计时包括GPU信息准备、MIP、参考映射、候选、配额生成/缓存、稳定评分、验证和提交；初始化、导入及审核计入整格wall。

| 负载 | 方法 | 被选次数 | 可行次数 | 迁移/纯节点 | aux-only | 实耗恢复总秒 | 训练加权rho | rho>1训练占比 |
|---|---|---|---|---:|---:|---:|---:|---:|
| saturn-2-supported80 | SIA-P | {'P': 346} | {'P': 346} | 210/73 | 0 | 18740.0 | 1.000 | 0.00% |
| saturn-2-supported80 | CAPRA-Fixed | {'F': 343} | {'F': 343} | 205/66 | 52 | 17315.0 | 1.161 | 16.51% |
| saturn-2-supported80 | CAPRA | {'F': 297, 'R': 7, 'K': 39} | {'F': 343, 'K': 334, 'R': 343} | 163/15 | 30 | 15045.0 | 1.150 | 15.36% |
| saturn-6-supported80 | SIA-P | {'P': 382} | {'P': 382} | 238/56 | 0 | 20330.0 | 1.000 | 0.00% |
| saturn-6-supported80 | CAPRA-Fixed | {'F': 377} | {'F': 377} | 245/87 | 73 | 20815.0 | 1.216 | 23.69% |
| saturn-6-supported80 | CAPRA | {'F': 335, 'R': 7, 'K': 35} | {'F': 377, 'K': 369, 'R': 377} | 185/16 | 55 | 16975.0 | 1.213 | 23.98% |

失败原因、F/K/R可行次数、Phi相对F分布、有限候选数/升级步数和缓存统计保留在每格summary及原始日志，未用平均值掩盖失败。

## 修复证据与解释范围

- 共享成本：实际应用成本CIFAR50/DeepSpeech25/BERT120；Sia-v2预测、映射、评分与执行一致。原始pilot能直接看到`restart penalty: 50.0`，每个主事件由独立审计再次对照应用源码。
- 节点身份稳定：只比较等价节点identity/swap，用真实费用，锁冲突拒绝、平局规范化幂等。共同参考与F再次处理不变；真实节点变化实际收费。
- 配额遗漏：冻结表fixtures证明1GPU CIFAR3→6CPU的rho=1.75，4GPU CIFAR12→18CPU的rho=1.415；两项BERT3→1CPU释放资源；耦合回收不拼未验证点，联合增配不漏掉共同CPU/RAM收益。
- 布局与选择：资源互补fixture能构造两侧BERT+CIFAR，8+2+2通过GPU-DP防碎片；仅F/K/R，F等于同状态Shared Fixed，失败候选整格丢弃、保留已求F；选中Phi不低于F。
- 执行与审计：输入current来自真实提交，锁剩余不重新收费；原始/锁修复/稳定参考分开记录。独立原始重放核对完整集合、GPU/batch、节点容量、rho一次、转换成本、先恢复后训练、完成与JCT恒等式。

上述机制fixtures是静态验证，不声称原主轨迹都发生。Phi是同状态/同模型的180秒启发式分数；全程GPU和batch轨迹会分化，不保证JCT，也不把逐轮预测节费相加当成两次运行的JCT差。

- saturn-2-supported80，CAPRA减Fixed：平均等待+0.00秒，训练+6.81秒，恢复-28.38秒。CAPRA选择{'F': 297, 'R': 7, 'K': 39}，F相对收益P95=0.6917。
- saturn-6-supported80，CAPRA减Fixed：平均等待-1.50秒，训练-12.75秒，恢复-48.00秒。CAPRA选择{'F': 335, 'R': 7, 'K': 35}，F相对收益P95=0.7247。

若主表收益有限，候选选择次数与相对F收益分布可衡量本模型是否常有布局机会；训练加权rho和boosted比例显示辅助增配实际生效程度；实耗恢复分解显示是否抵消训练收益。有限候选和贪心配额并非全局最优，单凭本六格不能证明布局空间不足或模型外真实性；没有固定状态精确参考的部分仍未确定。

## v1 历史与未覆盖范围

`v1_historical_reference.csv`单列旧结果（负载2：1141.6625/1048.425/1125.6125；负载6：1125.4625/1144.8375/1109.7），不代替v2同版本基线。共同节点稳定与成本修正本身会改变后续GPU轨迹，不能将跨版本差异全部算成新配额或R布局贡献。本轮未预登记额外消融，因此不加跑。

两条负载分别68/67个CIFAR，BERT仅3/5个，未包含Imagenet；原RAM响应在比例以上大体饱和。尚未验证RAM高于比例仍持续获益、多类强CPU/RAM互补、跨设备/batch敏感性真实变化、多节点和真实硬件。仅建议下一轮围绕实际证据挑选问题，不自动改输入或扩矩阵。

## 复现与结束状态

实验计费（pilot+六格及失败）23.56分钟；另保守预留60秒机制验证，预算占用24.56/120分钟。未静默延长单格900秒/进程960秒/6000轮限制。完整实验journal为`runs/capra_v2/budget_ledger.json`。

冻结清单`configs/experiment_manifest_v2.json`、精确运行源码`runs/capra_v2/CAPRA_V2_R1/frozen_source.zip`，代码与输入hash在冻结/最终核对文件中。所有原始事件、逐作业、资源、终止、审核和hash均位于六格目录。原始正负逐任务差异见`paired_jobs.csv`；无显著性声明、无H搜索、无自动重复种子、无远端推送。

在CAPRA根目录，用专属环境执行：

```powershell
.\.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -X utf8 -B -m capra.runner_v2 --input data/saturn-2-supported80.csv --method CAPRA --output runs/capra_v2/reproduce-new/CAPRA --wall-limit 900 --max-rounds 6000
```

输出目录必须不存在；严格冻结六格由`scripts/run_v2.py`执行，已有本轮目录不可原地重跑。安装依赖使用独立`requirements_v2.lock.txt`；数值核心仍保持v1固定版本。Matplotlib3.9.4仅用于本报告PNG/PDF，不参与调度。

本轮到此结束。下一步先解释同版本表中的训练/恢复和候选收益证据，再决定研究方向；不以需要获胜为由扩大搜索、改表或追加实验。

## 原始事件补充复核与实际结论

以下统计仅重读既有日志，不重新计算布局、不启动模拟；复现脚本为本运行目录`analysis_tools/supplement_v2.py`，数据为`raw_opportunity_analysis.json`及`application_time_and_jct.csv`。主表候选次数含空队列轮次，下表只统计非空决策。

| 负载 | 非空决策 | 选择F/K/R | K高于F | R高于F | 中间CPU训练区间 | BERT回收训练区间 | CIFAR整节点训练占比 |
|---|---:|---|---:|---:|---:|---:|---:|
| saturn-2-supported80 | 316 | 270/39/7 | 41 | 23 | 13 | 26 | 2.35% |
| saturn-6-supported80 | 330 | 288/35/7 | 36 | 29 | 27 | 61 | 3.42% |

直接的执行证据：负载2的round83，`cifar10-24`使用2GPU/15CPU/125GB，rho=2.075，实际训练60秒；负载6的round19，`cifar10-2`使用4GPU/21CPU/250GB，rho=1.585，实际训练60秒。它们不是旧CPU轴乘GPU数能够表达的点。BERT示例分别为round51的`bert-15`、round91的`bert-22`，均1GPU/1CPU/20.83GB且rho=1，实际训练60秒。详见JSON里的原始轮次与任务ID；区间计数不等于独立作业样本数。

**归因边界。** 配额升级确已在主实验生效，CAPRA训练时间加权rho为1.150/1.213，rho>1的训练时间占15.36%/23.98%；不能说CPU维度没有作用。额外布局机会在本三候选中有限：R只在23/29个非空轮次模型分数高于F、最终各采用7次，而K采用39/35次。该证据支持本轮多数额外收益与减少恢复相关，但不能证明更广布局或配额精确解没有收益；本轮没有全局oracle与新增消融，贪心配额局限和三布局搜索局限尚未分离。

“CIFAR单任务占满节点导致大部分辅助收益受限”的解释未被本数据支持：CAPRA中这种训练仅占CIFAR训练时间2.35%/3.42%，不能当作主要慢因。其他配额机会受同机资源、同版本Sia计划及响应模型约束，单靠空闲容量也不能推断存在可行的全面加速。

**尾部明确保留。** 负载2的CAPRA相对SIA-P-v2，P95增加5.70%、P99增加9.37%；相对Fixed，P95/P99分别增加9.15%/10.58%。其中DeepSpeech2组平均JCT由Fixed的3123.22秒升至3308.89秒，CIFAR组则由685.46降至636.99秒；这是组别结果分化，不是已证明的单条因果链。负载6的CAPRA相对SIA-P，P95增加0.36%、P99约下降0.05%，尾部近似持平；相对Fixed，P99下降9.74%。

同状态选择中有8/16轮出现个别任务窗口贡献下降，但全体Phi不低于F；另有2/1轮选中方案的未扣费sum-rho低于F。这说明实现允许通过整体收益交换个体短期进度，也说明不应把未扣费rho高低单独当成最终收益。它不能用于把这些轮次与全程JCT差直接等同。

**推荐下一步。** 优先用当前已有逐作业数据解释负载2的DeepSpeech2尾部及GPU/batch/恢复轨迹分化；再决定是否需要新的受控验证。当前均值已有收益，但没有尾部保证，不以加大H、重选负载或增加搜索来追求全指标获胜。本轮结束，不追加实验。未来尚需验证RAM高于比例仍有收益、强CPU/RAM互补、真实跨GPU/batch敏感性和实机条件。

离线原始审计可复制命令（拒绝v1输入，使用v2规则）：
```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts/replay_v2_audit.py runs/capra_v2/CAPRA_V2_R1/saturn-2-supported80/CAPRA
.\.venv\Scripts\python.exe -X utf8 -B runs/capra_v2/CAPRA_V2_R1/analysis_tools/supplement_v2.py
```

两个离线汇总工具是在实验结束后添加，不是调度运行文件，不改变冻结的1030项源码或已有运行。图表初稿与报告初稿保留在`report_revisions`；仅将时间分解图图例移到图外，数据不变。

本地v2分支创建至本次复盘墙钟约47.97分钟（含实施、验证、实验和图表；首次需求读取/只读核对另计）。模拟实验累计23.56分钟，含机制验证预留的预算计费24.56分钟，低于120分钟上限。

## 最终封存

1030个冻结运行文件及99个v1保护文件再次匹配；六格480个作业JCT时间恒等式和18项分位数复核通过。两张最终PNG已目视检查，PDF同时保留。本地分支创建至封存约51.07分钟，模拟实验23.56分钟；未推送、未启动额外实验。

图表：[均值](../runs/capra_v2/CAPRA_V2_R1/figures/v2_mean_jct.png)、[时间分解](../runs/capra_v2/CAPRA_V2_R1/figures/v2_time_decomposition.png)。最终索引为运行目录`EVIDENCE_INDEX.md`；完整校验清单为`evidence_hashes.json`。
