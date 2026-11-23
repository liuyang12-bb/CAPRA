# CAPRA R2 本地交付入口

基准 `81b1109ab1124feeac4e846003f4383b39143fc4`；分支 `capra/ablation-ram-r2`。旧main/v2/R1和原目录保持原字节。本轮未推送。

状态：COMPLETE_PASS，正式完成9/9，新增完成720/720。建议：FKR + ram_slack_v1，作为下一轮主研究版本；保留FK作轻量对照，不在本轮自动删R或改算法；仅提出选择建议，没有在结果后删除R或追加实验。

- [最终中文报告](docs/CAPRA_R2_RESULTS.md)
- [研究判断](docs/CAPRA_R2_INTERPRETATION.md)
- [冻结设计](docs/CAPRA_R2_DESIGN.md)
- [完整代码diff](docs/CAPRA_R2_CODE.patch)
- [后续验证计划，未执行](docs/NEXT_VALIDATION_PLAN.md)
- [新增九格结果](runs/ablation_ram_r2/results.csv)
- [含复用来源的分析结果](runs/ablation_ram_r2/analysis/results.csv)
- [全部比较与逐任务结果](runs/ablation_ram_r2/analysis/)
- [证据索引](runs/ablation_ram_r2/EVIDENCE_INDEX.md)
- [最终核对](runs/ablation_ram_r2/final_verification.json)
- [源码快照](runs/ablation_ram_r2/source_snapshot.zip)

共享实验时钟46.26/90分钟；工作副本创建到封存61.30分钟。所有模拟调用见simulation_calls.json，全部所属树清理和失败记录保留。

用户手动推送命令：

```powershell
git -C "D:\科研启航\CAPRA-ablation-ram-r2" push -u origin capra/ablation-ram-r2
```
