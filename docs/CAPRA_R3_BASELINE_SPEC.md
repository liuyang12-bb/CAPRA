# R3 Sia smart 适配基线

唯一基准0876dd916e1b25d2030233826968683da730a55f。SIA-SMART-P是“仓库内Sia smart placement在当前单节点、物理恢复锁和比例辅助资源模型下的适配基线”，不等同官方完整系统。

只有该实例使用SmartPolicy；原GpuStage、上游文件和R2方法不变。SmartPolicy继承相同optimize/optimize_mip/MIP，覆盖物理放置入口。原smart函数仅修正稳定降序排序中的jobname→x；两处eviction日志不改变行为。入口用int64独立容量副本逐次防负/超容量；空/零任务规范为空列表。raw任务集合、数量、单节点形状和容量必须先合法，才能进入共同物理锁修复；不合法或意外异常立刻失败，无fast/K回退。

共同锁修复只使用同次MIP的Y见证，保留GPU类型/数量；记录见证、修复前后、原因。然后执行原identity.reference、P-only比例CPU/RAM、commit_v2；锁定配额/剩余时间不改。非锁CPU=node.cpu*g/node.gpus，RAM同理；真实画像rho，不使用neutral。禁止K/R、preferred、NodeAllocator优化、RAM补充。审计字面白名单与该路径独立。

F/K/R、Phi、H180、EPS、恢复费、GPU-DP、RAM规则全部保持原文件。P-K/FK/CAPRA继续fast。FK真不调用R。费用包括节点迁移、恢复时间入JCT，aux-only仍零恢复。

smart来源、原函数SHA、适配SHA和精确diff见CAPRA_R3_SMART_PROVENANCE.json、CAPRA_R3_SMART.patch；不得将共同见证修复称为smart原生能力。
