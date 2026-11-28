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
