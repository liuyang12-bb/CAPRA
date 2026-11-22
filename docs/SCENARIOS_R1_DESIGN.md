# CAPRA v2：固定算法的六场景受控研究

基线为 `0b87934ae558960921889b01d14502155fb0c41c`，冻结运行核心来自 v2 的 `2517e5c`。独立分支 `capra/scenarios-r1`，独立工作副本 `D:/科研启航/CAPRA-scenarios-r1`。不推送，不改写 v1/v2 历史。本轮任务原文保留于 `SCENARIOS_R1_EXECUTION_ORDER.txt`。

## 研究设计

按固定顺序执行 w2_dense_original、w6_dense_original、w2_dense_cpu2、w2_dense_cpu6、w2_dense_cn、w2_dense_cm；每场景 SIA-P → CAPRA-Fixed → CAPRA，总计18格、每格80作业、种子0。没有参数搜索、选胜者追加实验或额外消融。六场景是机制覆盖，不是完整因子设计；CPU容量和敏感度只在W2检验。

两条原CSV的time按 `t_min+(t-t_min)/2` 用十进制精确计算，保留首到达、半秒、全部80行和非time字段。W2末到达10094.5，W6末到达11067。GPU任务、GPU性能模型、训练终止条件、batch和恢复成本均不变。

CPU/GPU取2、3、6，节点ID、每类型两节点、40GPU、4/8GPU结构及RAM不变。响应参考点始终3CPU/GPU、62.5GB/GPU，不随容量重归一化；CPU2原画像CIFAR/DS/BERT比例rho=.72/.66/1，CPU6为1.75/1/1。性能保底相对于当前场景节点的实际比例配额。

CN中CIFAR=C、DS=N、BERT=N；CM仅把DS由N改M。C把原CIFAR的RAM62.5截面沿RAM轴重复；N合法域恒1；M由 `c_equiv=3*m/62.5` 在C曲线插值得到原RAM采样点 `[.37,1,1.75,2.4,2.4]`，再沿CPU轴重复。20.83映射0.99984，用原插值边界取.37。轴、最小配额、ImageNet画像、插值器均不变。新表标记 synthetic_sensitivity，不是实际测量。原画像→CN是多项响应结构改变；CN→CM才是严格单因素RAM响应对照。

## 算法及输入边界

保护 gpu_stage.py、execution.py、identity.py、costs.py、node_allocator.py、placement.py、response.py、response_v2.py、contracts.py、tune.py、upstream.py 与整个third_party。Sia GPU决策、共同恢复成本、节点稳定、共享配额、F/K/R、H=180、排序和平局完全保持v2字节。保护原输入和历史证据哈希。

唯一运行接口变化是 runner_v2 增加 --cluster、--responses、--scenario-id、--run-version；省略时沿用原默认。start.json记录三个实际输入的绝对路径、仓库相对路径及SHA256。新增inputs.py统一输入定位；公共与v2审计读取实际文件并核对哈希，支持迁移工作副本后的相对路径重放。显式输入缺失或不符立即失败；旧日志才允许原默认规则，且必须核对旧哈希。

独立审计不调用Sia/NodeAllocator/FKR/成本函数，逐事件复核资源、batch、锁、评分/平局/保底、转换、训练rho一次、恢复期间无进展及JCT恒等式。原六格只在复制件中审计，原文件不写回。

## 预先验证与静态证书

原22测试和5新增测试，覆盖源CSV字段、拓扑、容量、响应正值/单调/参考点、CPU2/6倍率、CN/CM唯一差异、向量与独立插值一致、移机重放、缺失和坏哈希拒绝。另以CPU2/CM、CPU6/CM的20作业60轮短pilot核对传参和原始审计，不纳入正式主表，未完成JCT留空。

静态8GPU/24CPU/500GB节点的4C+2M+2N可分配20/2/2CPU与83.32/375/41.66GB，rho=1.53/2.4/1。它只证明可行机会。4C+4M时，当前候选器给C20CPU/83.32GB、M4CPU/250GB；连续M416.68GB可得1.50004，但不是无兼容当前点时的既有候选。保留这个算法局限，不加RAM点。动态分析另给实际轮次与单任务独立证书，不把静态例当动态结论。

## 冻结和预算

正式运行前生成独立 `configs/experiment_manifest_scenarios_r1.json` 和精确 `frozen_source.zip`。记录全部运行文件、输入、算法保护、依赖、环境/求解器版本及生成器哈希。归档源码可独立恢复，不依赖开发目录未记录差异。

同一Windows单调时钟截止从本轮准备测试开始7200秒，覆盖准备运行、核验、写盘、清理及正式运行，中间开发时间也保守计入；不因重试重置。每格900秒runner、960秒进程上限、6000轮；给最后清理预留30秒。沿用30轮无进展、连续3个非空决策超过30秒、STOP_REQUEST止损。只终止本轮拥有的进程树，使用Windows Job Object，子进程挂起创建、分配Job后才恢复，关闭时清理全部后代；真实孙进程验证记录在development。算法/审计失败停止后续格，有限环境重试另目录且预算共用；本设计不预设自动重试。

控制器耗时不计模拟JCT；真实恢复计入。三方法使用同场景完全相同输入和成本。只有80/80才报告整体mean/P50/P95/P99/makespan。主决策开销只用非空轮次，空轮统计如有则单列all_rounds。

## 分析口径

改善率=`100*(1-JCT_method/JCT_baseline)`，正为更快。同场景分别比较Fixed/SIA、CAPRA/SIA、CAPRA/Fixed；原六格单列参考。报告训练/等待/恢复和尾部，不能把同状态预测节费相加成动态JCT因果量。

从原始执行训练段计算时间加权rho、rho/rho_prop、超过本场景比例rho的训练份额，以及固定另一资源的CPU/RAM条件差及正增益训练份额。条件差有耦合时不可相加。节点和GPU类型资源占用积分包括训练及恢复，不是硬件忙碌率。

机会逐层统计实际应用及C/N/M训练/GPU时间、共同GPU选择/同类型/可组合/锁/同机/目的节点容量、F/K/R可行/选择/Phi分布、R未扣恢复总rho、迁移/纯节点/aux更新、可用空闲资源的合法单任务加速证书。机会证书逐个成立，不将共享同一空闲资源的增益相加，不宣称穷尽布局或全局最优。F已经同机不等于F全局充分利用，R没找到也不证明没有更优布局。

CN/CM SIA-P必须工作负载和集群哈希相同、成本相同、逐作业完整统计和语义执行轨迹一致；排除墙钟、路径、场景ID和缓存等元数据。若不一致首先调查输入/数值实现，不能解释为RAM调度收益。
