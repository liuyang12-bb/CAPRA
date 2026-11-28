# CAPRA Direct R5 本地交付

**实现完成；限定验证完成；正式性能实验 NOT_RUN；未推送。**

基准`ffa953fb9cd12773992559512d85065bbd26b7b2`，独立分支`capra/direct-placement-r5`。13组必要测试通过；固定smoke1 PARTIAL_SMOKE（6/8，60轮），smoke2 COMPLETE_SMOKE（8/8，46轮），两者原始审计PASS。

- [实现与验证中文报告](docs/CAPRA_DIRECT_R5_IMPLEMENTATION_REPORT.md)
- [算法设计与预登记](docs/CAPRA_DIRECT_R5_DESIGN.md)
- [Direct核心](src/capra/placement_direct_r5.py)
- [布尔完成性](src/capra/feasibility_direct_r5.py)
- [运行入口](src/capra/runner_direct_r5.py)
- [独立审计](src/capra/audit_direct_r5.py)
- [必要测试](tests/test_direct_r5.py)
- [固定验证合同](configs/direct_r5_validation.json)
- [原始日志与所有attempt](runs/direct_r5/validation/)
- [累计预算账本](runs/direct_r5/validation_budget.json)
- [源码快照](runs/direct_r5/snapshots/)
- [实际统计](runs/direct_r5/analysis/implementation_results.json)
- [最终证据核验](runs/direct_r5/final_evidence_checks.json)
- [封存与证据哈希](runs/direct_r5/evidence_hashes.json)

不使用此smoke的JCT推导正式性能收益。工作树保留R4及更早3094个跟踪文件字节。环境为独立.venv，依赖版本从R4复制、仅新editable路径指向R5，旧环境不变。

手动推送：`git -C "D:/科研启航/CAPRA-direct-placement-r5" push -u origin capra/direct-placement-r5`。
