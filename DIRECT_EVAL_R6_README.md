# CAPRA Direct R6 正式对照入口

有效新正式运行8/8，合格R4参照12/12；算法基准`b40cdefdff27d46d8044510652a557e8d7599920`，执行HEAD`85d1c1b7c51f7d44f6abdfae5fe5663cc1d3c051`。所有负结果保留；未推送。

- [中文结果报告](docs/CAPRA_DIRECT_R6_RESULTS.md)
- [设计与预登记](docs/CAPRA_DIRECT_R6_DESIGN.md)
- [冻结manifest](configs/experiment_manifest_direct_eval_r6.json)
- [正式单元与全部attempt](runs/direct_eval_r6/CAPRA_V2_DIRECT_EVAL_R6/)
- [矩阵ledger](runs/direct_eval_r6/matrix_ledger.json)
- [共享预算](runs/direct_eval_r6/budget_ledger.json)
- [R4复用资格](runs/direct_eval_r6/historical_reuse/)
- [结果、配对与机制表](runs/direct_eval_r6/analysis/)
- [最终核验](runs/direct_eval_r6/final_verification.json)
- [可移植复核脚本](scripts/verify_direct_eval_r6.py)

固定原始输入与R5算法字节保持。新verify/report只读封存证据，不调用生产调度器或训练；复核从当前ROOT解析相对路径，不要求旧磁盘路径或旧分支存在。

手动push：`git push -u origin capra/direct-evaluation-r6`。


## 本轮结论与复核命令

Direct四场景的完整80作业平均JCT均优于独立F-only及Smart，但四场景均值均落后于FK/FKR。
相对F-only平均改善15.52%/10.17%/5.48%/2.99%；S8-CM的P99反而退化5.56%，最大个体退化1920秒。
这是两个trace、固定seed和冻结响应模型下的仿真结果，不作真实硬件或普遍最优结论。

在本仓库根目录，复核和分析重建分别使用：

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts/verify_direct_eval_r6.py --manifest configs/experiment_manifest_direct_eval_r6.json
.\.venv\Scripts\python.exe -X utf8 -B scripts/report_direct_eval_r6.py --manifest configs/experiment_manifest_direct_eval_r6.json
```

手动verify只写新的verification目录，不改封存latest回执；report只写新的analysis_rebuild目录。
两者均不启动生产调度、GPU MIP或Job.step。

正式入口的原窗口续作命令如下，仅适用于尚未封存、原绝对截止时间未到的状态：

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts/run_direct_eval_r6.py --manifest configs/experiment_manifest_direct_eval_r6.json --resume
```

本轮已完成并封存，正式入口会在触碰预算前拒绝再次续作。新实验需要独立授权、输出目录和预算，不能重置本轮。
本轮最终完整性与图表检查见`runs/direct_eval_r6/final_verification.json`，各次失败和修复记录全部保留。
