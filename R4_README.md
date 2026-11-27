# CAPRA R4 本地交付入口

状态：COMPLETE_PASS。基准 `5af0bdb6b86b797225908f717b5b9324cd48a539`；独立分支 `capra/pressure-opportunity-r4`。实际完整12/12格，新增完整960/960作业，全部格要求实际运行，无等价复用。R3算法及历史字节保留；本轮未推送。

- [中文主报告](docs/CAPRA_R4_RESULTS.md)
- [预注册设计](docs/CAPRA_R4_DESIGN.md)
- [下一阶段决定](docs/CAPRA_R4_NEXT_PLAN.md)
- [准确代码补丁](docs/CAPRA_R4_CODE.patch)
- [输入生成与逐行来源](data/pressure_r4/)
- [实际物理结果](runs/pressure_r4/results.csv)
- [含历史参照的结果与来源](runs/pressure_r4/analysis/)
- [严格机会漏斗](runs/pressure_r4/analysis/opportunity_funnel.csv)
- [代表作业与动态轨迹](runs/pressure_r4/analysis/opportunity_cases.json)
- [有限小状态审查](runs/pressure_r4/analysis/bounded_layout_reviews.json)
- [图件PNG/PDF](runs/pressure_r4/figures/)
- [源码快照](runs/pressure_r4/source_snapshot.zip)
- [最终核验](runs/pressure_r4/final_verification.json)
- [时间账本](runs/pressure_r4/delivery_clock.json)
- [证据哈希](runs/pressure_r4/evidence_hashes.json)

手动推送：

```powershell
git -C "D:/科研启航/CAPRA-pressure-opportunity-r4" push -u origin capra/pressure-opportunity-r4
```
