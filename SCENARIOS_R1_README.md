# CAPRA v2 场景实验 R1 入口

本工作副本对应本地分支 `capra/scenarios-r1`，基于已上传v2提交 `0b87934`。原工程 `D:/科研启航/CAPRA`、main上的v1、capra/v2-20261122上的v2均保持原样。本轮不推送GitHub，不修改调度算法。

- [实验报告](docs/SCENARIOS_R1_RESULTS.md)：原六格参考、新18格、逐项研究结论、负结果、RAM动态漏点和复现命令。
- [冻结设计](docs/SCENARIOS_R1_DESIGN.md)：场景规则、输入接口、数值口径和预算边界。
- [六场景配置](configs/scenarios_r1.json)、[派生数据](data/scenarios_r1/)和[冻结清单](configs/experiment_manifest_scenarios_r1.json)。
- [结果表](runs/scenarios_r1/CAPRA_V2_SCENARIOS_R1/results.csv)、[证据索引](runs/scenarios_r1/CAPRA_V2_SCENARIOS_R1/EVIDENCE_INDEX.md)、[最终核对](runs/scenarios_r1/CAPRA_V2_SCENARIOS_R1/final_verification.json)。
- [全部原始结果](runs/scenarios_r1/CAPRA_V2_SCENARIOS_R1/)及[frozen_source.zip](runs/scenarios_r1/CAPRA_V2_SCENARIOS_R1/frozen_source.zip)。

18/18格、1440/1440作业、所有原始审计通过；CN/CM SIA-P逐作业和184轮语义轨迹严格一致。累计实验预算78.61/120分钟（准备测试、准备运行、原六格复制重放、开发间隔、正式执行/核验/写盘/清理均由同一单调时钟涵盖）。后续分析不启动新模拟。

CAPRA相对同场景SIA-P的平均JCT改善为17.55%、21.28%、15.78%、11.93%、20.93%、22.18%；相对Fixed为13.65%、14.71%、9.77%、12.67%、11.45%、5.88%。这是一组受控仿真，不是实机或广泛负载结论。CPU6/Fixed均值与CPU6/CAPRA P95负结果保留。

动态RAM候选漏点分别出现在CM/Fixed的64轮、CM/CAPRA的56轮。证书固定其他任务与位置，不能累计共享空闲资源的预测收益；本轮未修复该算法局限或追加运行。

运行接口只改 `src/capra/runner_v2.py`、`audit.py`、`audit_v2.py` 并新增 `inputs.py`。其余调度算法和整个上游源码与v2哈希相同。独立分析、报告、终检分别为 `scripts/analyze_scenarios_r1.py`、`report_scenarios_r1.py`、`verify_scenarios_r1.py`。
