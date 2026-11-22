# CAPRA 独立项目本阶段报告

项目绝对路径：`D:\科研启航\CAPRA`。独立本地Git工程和`.venv`已交付；未创建远端、推送或修改旧MELD项目。本阶段必要验证9项通过；六格中6格全量完成、6格通过原始事件复算。没有自动扩展矩阵。

## 主要结果

负值表示平均JCT降低。全部完成才报告整体JCT/P95/P99/makespan，单位为模拟秒；均为本CAPRA项目的新运行结果。

| 负载 | 方法 | 完成 | 平均JCT | 相对SIA-P | P95 | P99 | makespan |
|---|---|---:|---:|---:|---:|---:|---:|
| saturn-2-supported80 | SIA-P | 80/80 | 1,141.66 | +0.00% | 3,694.85 | 4,296.21 | 20,600.00 |
| saturn-2-supported80 | CAPRA-Fixed | 80/80 | 1,048.43 | -8.17% | 3,081.50 | 4,061.94 | 20,583.00 |
| saturn-2-supported80 | CAPRA | 80/80 | 1,125.61 | -1.41% | 3,583.75 | 4,483.67 | 20,583.00 |
| saturn-6-supported80 | SIA-P | 80/80 | 1,125.46 | +0.00% | 2,898.80 | 3,613.17 | 22,769.00 |
| saturn-6-supported80 | CAPRA-Fixed | 80/80 | 1,144.84 | +1.72% | 2,895.25 | 3,551.32 | 22,676.00 |
| saturn-6-supported80 | CAPRA | 80/80 | 1,109.70 | -1.40% | 2,924.40 | 3,221.95 | 22,676.00 |

- saturn-2-supported80：CAPRA相对SIA-P的平均JCT变化-1.41%，相对Fixed变化+7.36%；Fixed相对SIA-P变化-8.17%。
- saturn-6-supported80：CAPRA相对SIA-P的平均JCT变化-1.40%，相对Fixed变化-3.07%；Fixed相对SIA-P变化+1.72%。

这是两份80作业、固定合成辅助响应和单节点域的结果，不能自动推出实机、所有工作负载或投稿充分性；无显著性或普遍获胜声明。CAPRA-Fixed与CAPRA的后续Sia计划会因进度分化而不同，二者差异反映本轮动态放置策略的整体效果，并非严格固定全程GPU轨迹的纯放置因果效应。受控例才使用相同GPU输入。

## 真实开销与事件

决策为从准备到提交的完整墙钟，单独报告，不扣入模拟执行时间；整格墙钟包含子进程导入、初始化、训练推进、决策和首次原始审核，不将全部wall当作优化器耗时。迁移/恢复/重配置则实际扣模拟时间。

| 负载 | 方法 | 决策中位/秒 | P95/秒 | 最大/秒 | 整格墙钟/秒 | 节点迁移次数 | TUNE回退事件数 | 共同物理修复轮数 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| saturn-2-supported80 | SIA-P | 0.0335 | 0.0994 | 0.1986 | 240.71 | 326 | 0 | 4 |
| saturn-2-supported80 | CAPRA-Fixed | 0.0355 | 0.1064 | 0.1932 | 221.50 | 267 | 402 | 1 |
| saturn-2-supported80 | CAPRA | 0.0354 | 0.1402 | 0.1783 | 210.48 | 335 | 436 | 1 |
| saturn-6-supported80 | SIA-P | 0.0278 | 0.1020 | 0.2457 | 227.82 | 365 | 0 | 8 |
| saturn-6-supported80 | CAPRA-Fixed | 0.0302 | 0.1581 | 0.2995 | 214.99 | 404 | 419 | 12 |
| saturn-6-supported80 | CAPRA | 0.0333 | 0.1551 | 0.3286 | 221.66 | 387 | 412 | 9 |

回退事件可能在同一轮出现多个，不等于失败轮数；迁移按实际节点身份变化记录，含同类型节点迁移。物理修复使用共同Sia阶段的同目标节点可行性见证，不将修复后的节点声称为未改变的首次输出。逐轮计划、修复前后、锁和配额均保存在各格`events.jsonl.gz`，节点表为`node_resources.csv`；各格`summary.json`提供分类型事件计数及实际配额资源时间积分。

`runs/main_v1/time_decomposition.csv`列出各方法平均等待、训练、恢复时间；`paired_jobs.csv`保留全部正负逐作业差异。JCT恒等式、进度连续、响应只乘一次、checkpoint锁、完整集合与逐节点容量由raw复算校验，不用runner终值代替原始证据。`deep_audit.json`另以独立脚本跨轮推导应有的锁、节点迁移、应用恢复成本及先恢复后训练时钟，不只相信每轮自报锁集合。

- saturn-2-supported80，CAPRA减Fixed：平均等待+2.25秒、训练+47.81秒、恢复+27.12秒，合计+77.19秒。
- saturn-6-supported80，CAPRA减Fixed：平均等待-3.00秒、训练-4.64秒、恢复-27.50秒，合计-35.14秒。

训练项差异可包含后续GPU类型/数量、batch和辅助配额轨迹分化，恢复项差异也依赖应用与迁移事件；这些是精确核账，不是固定状态反事实，不能把全部差异归给单一节点选择规则。

## 小验证和执行边界

两节点四任务控制例：Fixed平均JCT=88.0秒，CAPRA自由放置=65.0秒。四任务的原GPU计划均为2GPU/单节点、batch128、剩余600单位；互补放置每节点CPU敏感任务8CPU/50GB与RAM敏感任务4CPU/200GB。自由方案中两次同类型节点迁移各收10秒，实际Sia Job.step执行完成时刻60/70/70/60；Fixed为80/80/96/96。这是执行单指定的合成机制例，不是实测画像，也不声称Sia必然选该GPU计划。

neutral同部署无额外训练收益；恢复/等待不被rho缩放；锁定位置与配额不变；不完整集合在提交前拒绝；仅配额变化不计GPU迁移；实际Sia锁约束和完整返回通过。完整测试日志在`runs/validation/contracts_test.log`。

官方Sia smoke完成3/3，平均JCT592秒，仅验证工程跑通。CAPRA短pilot80轮耗时33.37秒，10/12完成（含尚未到达/未完成的短窗口），整体JCT留空，不搬入主表。正式前估计及止损限制已写入冻结manifest；没有按结果调整画像、输入、训练量或算法。

## 来源、数据与可复现性

- 官方Sia：[siasosp23/artifacts](https://github.com/siasosp23/artifacts)，实际提交`aaf7a0de7b6cb5eab06ea020467ede5d2fd18e70`。
- 官方Synergy：[msr-fiddle/synergy](https://github.com/msr-fiddle/synergy)，实际提交`1bb2bed6edc9c5f953d0b7f0a40e4fdad053489c`；规则核对来自官方`simulator/resources/cluster.py`及[原论文](https://www.usenix.org/system/files/osdi22-mohan.pdf)。
- CAPRA冻结代码提交`2e8e4a068bb3db01c0192216e3c7ac540d56b17e`；manifest SHA256 `a0033fdfe35885ac9c753af3da3ffbca10d597ad50c44a54607c90cc2cb24ae1`；1010个冻结文件最终哈希匹配。

- `data\saturn-2-supported80.csv`：80作业，原到达101.0–20088.0秒，应用数{'cifar10': 68, 'imagenet': 0, 'bert': 3, 'deepspeech2': 9}；SHA256 `25ed84bc64109a555f241eb8ad1bf38837787a85aee4f60b203143a5d5750aa1`。
- `data\saturn-6-supported80.csv`：80作业，原到达22.0–22112.0秒，应用数{'cifar10': 67, 'imagenet': 0, 'bert': 5, 'deepspeech2': 8}；SHA256 `40f7aa481f693525f0c7f828b71a52c858a590aa0dc157ac6e6fffb2b583778f`。

选择规则是在主结果前按编号选最先有80条支持行的两份上游Saturn负载，应用限四种数据并行模型、原请求1..8GPU；保留原到达、请求和batch，训练沿用原应用终止标准。负载1仅70条支持行，不足80，故按相同规则选2和6，不按收益选择。

实际两份输入中imagenet均为0，cifar10分别68/67个，BERT仅3/5个；覆盖偏向CPU敏感映射模型，尚不能单独验证RAM敏感负载上的放置收益或任意资源组合的普遍性。

GPU性能、梯度效率、batch选择和在线更新继承Sia；CPU/RAM使用Synergy公开一GPU模板，cifar10→res18、imagenet→res50是模型族映射。每GPUCPU/RAM转移、跨GPU类型与batch保持相同归一化响应是显式合成假设。比例点3CPU/62.5GB归一为1；没有全GPU/batch实测覆盖或新硬件画像声明。

原版权和Synergy MIT文件保留；Sia根仓库未给出统一许可证，不将自身声明扩张覆盖上游，具体文件保留原版权头。适配细节和限制见`docs/DESIGN.md`及`docs/sia_upstream.patch`。本版peer回退将候选节点所有未锁peer统一重置比例，包括原本低于比例者，是比官方excess选择更保守的节点级适配，可能浪费辅助资源；不将本实现等同完整原Synergy系统。

## 实际命令和下一步

本次从CAPRA自己的环境执行：

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts/check_small.py
.\.venv\Scripts\python.exe -X utf8 -B scripts/freeze_experiment.py
.\.venv\Scripts\python.exe -X utf8 -B scripts/run_matrix.py
.\.venv\Scripts\python.exe -X utf8 -B scripts/deep_audit.py
.\.venv\Scripts\python.exe -X utf8 -B scripts/build_report.py
```

冻结和主矩阵命令不应在已有目录原地再次执行。复现单格使用README的新输出目录命令；每格`process.json`保留实际完整命令。原始和审计哈希在`output_hashes.json`和`audit_hashes.json`；总核对见`runs/main_v1/final_verification.json`。

收益依场景而异：本轮CAPRA相对SIA-P两份均只有约1.4%的平均JCT收益，Fixed在一份改善、另一份退化，尚不能主张自由放置普遍更优。下一项最值得做的是基于已有原始事件，对相同GPU计划核对Fixed/free的配额、节点选择和迁移代价，解释为什么负载2自由放置训练与恢复时间增加、负载6的Fixed恢复时间反而增加；先完成归因，再决定保留哪一版本。当前不扩大矩阵、不改画像或增加搜索。

扩展负载、实机或新机制需要下一轮明确任务，本轮到此结束。
