# CAPRA v0.1 方法与适配边界

CAPRA 是独立工程；本轮无旧项目算法、输入、环境或运行时导入。官方来源与提交见 `upstream_versions.json`。运行源码在 `third_party/sia/sia-simulator` 和 `src/capra`。Synergy 部署代码仅作为 TUNE 核对和画像来源，不装其旧部署依赖。

## 两阶段

1. `gpu_stage.py` 调用官方 `SiaPolicy.optimize`。保留 p=-0.5 goodput、公平项、未分配惩罚、配置变更惩罚、吞吐投影与在线模型学习；没有 ETA 或第二套准入。GPU 形状限定为单节点的官方幂二配置：aws 1/2/4，dgx-ext、rtx 1/2/4/8。Sia 的批大小由 `Job.update_local_bsz` 得到只读候选快照；第二阶段不搜索 batch。
2. `tune.py` 接收选中作业完整集合与固定 GPU 类型/数/shape。按 GPU 数降序、名称打破平局，尝试画像最优辅助需求。节点使用动态剩余 GPU 最少的 best-fit，节点ID打破平局；不是固定ID顺序假称best-fit。失败时依次回退当前任务比例配额、相关节点上非锁定peer的比例配额，最终用完整可行比例基准；从不提交部分集合。

CAPRA-Fixed 与 CAPRA 仅 `placement mode=fixed/free` 不同，共用画像、配额选择、保护与回退代码。SIA-P 使用同一Sia阶段、原节点放置与比例配额。完整运行进度分化后，三者后续 GPU 计划允许不同。

## 与 Synergy 官方实现的差异

官方 `simulator/resources/cluster.py:575` 起的 `_tune` 先尝试demand，然后将当前作业改成fair share，再调整相关peer，最后重试。`_top_synergy_gpus_placement` 用剩余GPU最少堆减少碎片；`_make_fair_share` 将CPU、内存等同时重置比例值。

CAPRA 是这些规则的清晰重实现，未导入整套部署/资源类。仅支持单节点、GPU/CPU/主机RAM，省略存储带宽；每个作业只接受一个节点；事务式候选拷贝替代原实现的即时deallocate/reallocate。peer只改辅助配额不交换节点；比例保护使用同一响应模型复核。节点排序、peer范围和上述限制均为适配，不声称逐语句等同官方系统。

## 共同可行性与锁

没有恢复锁时，沿用原 Sia GPU 放置。在恢复锁存在时，在原 Sia MIP 添加共同物理可行性约束：二进制节点见证、锁定位置/配额，其他任务保守地使用比例辅助配额作为可行性基准。三方法使用相同规则，保留 Sia 目标；CPU/RAM不是第二阶段新MIP目标。若原始节点安排违反物理锁或此基准容量，使用同一次Sia求解的完整节点见证修复并记录前后节点，不能宣称从未改变原节点计划。

固定GPU接口是该共同处理后的最终GPU计划。`contracts.validate` 对完整集合、GPU类型/数量/shape、逐节点容量和精确恢复锁做统一核验。候选不改变live Job；统一提交。完整比例回退失败属于显式正确性失败，不删任务、不沿用未经本轮验证的旧计划。

## 执行和时间

保留官方 Sia Job 的epoch/梯度效率/吞吐/在线性能拟合/批大小更新逻辑，只在最终训练goodput上乘一次rho；不改变恢复与等待时钟。保留上游epoch时间取整，并在raw segment中明确取整残差。

物理节点ID变化属于迁移，即使GPU类型与shape不变，也收取相同的应用恢复代价。仅辅助配额变化假定可在线调整、不触发GPU迁移。启动、恢复、重配置均消耗模拟时间；恢复期间锁定节点与全部配额。暂停不训练；没有额外的永久服务/有序准入规则。

完整决策计时从job info准备开始，覆盖GPU MIP、batch快照、画像、节点、辅助配额、验证与提交；初始化/导入属于整格墙钟而非每轮决策。调度墙钟不额外扣进模拟训练时钟，单独报告。每格最多900秒、6000轮；连续30轮无任何训练推进或3次决策均>30秒会止损。优化后端每次10秒上限；无可验证解则明确失败，不伪报成功。

## 响应与数据

`data/responses.json`保存Synergy一GPU公开模板：cifar10映射res18；imagenet映射res50；bert与deepspeech2对应bert和deepspeech。前两项是模型族映射，不是同模型实测。CPU轴1/2/3/4/5/6/9/12/24，RAM轴20.83/62.5/125/187.5/250 GB，来自官方jobs/job.py。

按每GPU配额做双线性插值，在3 CPU/62.5GB归一化为1。跨GPU数线性转移，跨GPU类型与batch保持同一归一化敏感性，均为合成假设；Sia原GPU吞吐视为比例参考。CPU/RAM画像不反向污染Sia GPU参考画像；GPU模型继续按官方逻辑学习，第二阶段单独使用辅助模型。没有新实机画像或全GPU/batch实测覆盖声明。

两份负载按数值编号选择最先有80个支持行的Saturn文件，最终为2和6。支持规则：四种上述数据并行应用，原请求1..8 GPU。各取按原到达时间、原行号排序的前80；保留到达、请求、batch及原训练终止标准，不缩短训练。workload-1仅70个合格行，因此排除；不依据调度结果选择。

## 上游兼容性与许可证

`sia_upstream.patch`完整记录单节点域、SciPy/HiGHS替代CBC、物理约束钩子、训练rho和segment日志改动。Sia仓库根未提供整体LICENSE文件；各源文件的原版权/Apache头原样保留，不把本工程的许可声明强加给上游。Synergy保留官方MIT LICENSE.md。没有以“公开仓库”代替许可说明，也未做远端发布。

本轮不含跨节点单作业、流水线、交换搜索、全维联合搜索、新ETA目标或旧方法对照。
