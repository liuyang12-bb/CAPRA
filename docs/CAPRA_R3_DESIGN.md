# CAPRA R3 预注册设计与验证

按CAPRA_R3_EXECUTION_ORDER.txt固定执行15次正式运行、登记4次CM比例逻辑复用。两阶段第一格前一起冻结。A三次smart：W2 original、W2 CM、W6 original。B顺序：Saturn7 original smart/P-K/FK/FKR，再CM FK/FKR；Saturn8 original FKR/FK/P-K/smart，再CM FKR/FK。FK/FKR统一ram_slack_v1。40GPU、6节点、单节点作业、60秒周期、H180、seed0、依赖和线程1不变。旧W2/W6原画像FK/FKR legacy仅历史背景；不冒充修复版。原画像和CM是两种冻结环境，非严格RAM单因素消融。

首次准备测试前建立7200秒连续单调预算，含测试/回放/输入/冻结/两次短冒烟/15格/审计/写盘和进程树清理。每格900秒runner、960秒所属树、6000轮，实际还受剩余预算减30秒约束。串行、Windows Job Object挂起创建再归属，终止整个所属树。原STOP_REQUEST、全部到达后30轮无进展、三次非空>30秒保持。无正式重试；正确性/环境/预算失败即停止剩余并保留NOT_RUN。离线报告计时单列，不追加模拟或调参。

验证清单（首次测试前登记）：原33测试+新增smart排序/稳定平局、保留/变化/新增/满节点/碎片/重装箱、空零/有符号/非法raw、固定GPU fast/smart配置不变、隔离、共同锁/费用、独立审计反例。R2源逐一选前2/后2非空、首次K/R、首次锁、首次K不可行，先登记全体选择再回放，去重且不重跑旧负载。原始源码/输入/历史2000文件逐一保护。旧RAM证明只读复核，不重做288状态。最多两次W2已开发负载短冒烟：smart original、CAPRA CM，各12作业/30轮/90秒runner/120秒所属树；内部Job.step逐次记录，不完整指标为空。

holdout仅Saturn7/8，按R2已登记源hash与原行号，支持四应用、原GPU1..8，按原time/源行号取80，原字段和到达不变，不压缩。输入/画像/算法/顺序不得据A结果改动。

复用门槛：比例点两画像实际求值严格相等且为1，轴/合法域一致；原代码无非比例偏好/优化依赖；相同初始状态→GPU/MIP/放置/锁/费用/batch相同→rho1下进度同→下一状态同的归纳证明；旧P-K全轨迹控制和新入口回放，A的W2 smart original/CM全语义严格控制；holdout各源完整80/80且审计所有候选/执行精确比例。仅排除计时/缓存/元数据，保留所有调度和进度字段。失败即停，不扩成19次。

逻辑复用必须executed=false/EQUIVALENCE_REUSED、源run/path/input/events/profile与目标profile哈希、证书SHA；不复制原日志，时间仅源original观测。新增执行1200作业，不将1520逻辑作业计独立样本。原方法/历史来源分别标注。收益100*(1-method/base)，保持负值、尾部、个体退化、完整开销。单轨迹派生画像非独立重复；合成画像非硬件实测；两个同源trace非多来源生产泛化。结果后只建议FK/FKR，不改算法。
