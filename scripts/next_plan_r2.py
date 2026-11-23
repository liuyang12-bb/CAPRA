"""Read-only Saturn7/8 eligibility inspection; no derived workload or simulator."""
from collections import Counter
import csv,re
from r2_utils import *
def main():
    folder=ROOT/'third_party/sia/sia-simulator/workloads/saturn';supported={'cifar10','imagenet','bert','deepspeech2'};items=[]
    files=sorted(folder.glob('workload-*.csv'),key=lambda p:int(re.search(r'workload-(\d+)',p.name).group(1)))
    for number in (7,8):
        path=next((p for p in files if p.name==f'workload-{number}.csv'),None)
        if path is None:items.append(dict(workload=number,status='MISSING_SOURCE'));continue
        with path.open(encoding='utf8',newline='') as f:rows=list(csv.DictReader(f))
        eligible=[(i,r) for i,r in enumerate(rows) if r['application'] in supported and 1<=int(r['num_replicas'])<=8]
        eligible.sort(key=lambda ir:(float(ir[1]['time']),ir[0]));chosen=eligible[:80] if len(eligible)>=80 else []
        items.append(dict(workload=number,status='ELIGIBLE_FOR_FUTURE_PLAN' if len(eligible)>=80 else 'INSUFFICIENT_DO_NOT_PAD',source=path.relative_to(ROOT).as_posix(),source_sha256=sha(path),source_rows=len(rows),eligible_rows=len(eligible),
            planned_rows=80 if chosen else 0,source_zero_based_indices=[i for i,r in chosen],application_counts=dict(Counter(r['application'] for i,r in chosen)),
            first_original_arrival=float(chosen[0][1]['time']) if chosen else None,last_original_arrival=float(chosen[-1][1]['time']) if chosen else None,
            fields_unchanged=True,generated_workload=False,executed=False))
    dump(RUN/'analysis/next_candidate_inputs.json',dict(status='PLAN_ONLY',selection='Numeric file order7 then8; supported original apps; original requests1..8; first80 by original time then source zero-based row; no copies/padding',candidates=items))
    recommendation=load(RUN/'analysis/recommendation.json') if (RUN/'analysis/recommendation.json').exists() else dict(recommended='Await R2 evidence judgment')
    lines=['# 下一轮验证计划（本轮不执行）','',f"R2建议：{recommendation['recommended']}。先据R2结论冻结最终主算法、RAM规则、恢复成本和依赖，再登记新矩阵。本轮没有生成Saturn7/8派生CSV、没有运行这些负载。",'',
       '## 已只读核对的固定候选来源','', '|原文件|原行数|合格行数|可选80|SHA256|','|---|---:|---:|---|---|']
    for item in items:lines.append(f"|Saturn{item['workload']}|{item.get('source_rows','—')}|{item.get('eligible_rows','—')}|{item.get('planned_rows',0)==80}|{item.get('source_sha256','MISSING')}|")
    lines+=['','候选清单：runs/ablation_ram_r2/analysis/next_candidate_inputs.json，包含原始行索引和哈希。排序和筛选沿用原规则：数值文件顺序，支持cifar10/imagenet/bert/deepspeech2，原请求1..8GPU，按原time和源行号取前80；保持全部字段和原到达。任何候选不足80则明确保留不足，不复制作业、不换有利文件、不根据R2胜负改选。','',
       '## 优先级与必要证据','',
       '1. 首先在固定Saturn7/8上验证冻结后的主方法。建议至少保留SIA-P及SIA-P-K作为位置保留对齐背景，再比较所选资源方法；是否保留FKR以R2结论预先固定。依然同场景同恢复/画像/种子/线程，报告逐任务尾部和完整开销，不提前承诺收益。具体格数和预算在下一轮单独登记。',
       '2. 补足外部资源感知基线。明确Synergy-TUNE等方法与Sia的GPU/batch/恢复接口差别，建立可执行公平适配和独立审计后再比；不能把只重排位置的内部消融当作外部基线。',
       '3. 画像真实性及误差、恢复成本敏感性。优先补独立可追溯的CPU/RAM实测或公开真实画像；合成敏感度只支持机制实验。再预先登记有限误差/恢复成本对照，不能随结果调强画像。',
       '4. 规模扩展必须先修改并证明范围：当前每GPU类型最多两个等价节点、单节点任务、4/8GPU结构。GPU-DP和身份稳定均依赖该范围，40GPU结果不代表大规模/跨节点泛化；本轮不实现或运行这些扩展。','',
       '## 论文组织建议','',
       '方法：继承的Sia GPU性能/自适应与共同费用 → 比例位置保留对照 → 固定/保留/可选重排布局 → 共享辅助分配 → 有界RAM剩余容量补充及步数证明 → 执行、恢复和独立审计。',
       '实验：来源/锁定环境与版本 → A三场景五方法（figures/A_five_methods）→ 匹配位置保留后的资源增量与R开销（figures/R_increment_overhead）→ CM修复前后时间账本（figures/CM_ram_before_after）→ 逐任务退化与尾部 → 局部证书及限制。',
       '待补：新负载、外部基线、真实画像/误差和成本鲁棒性，以及扩展后复杂度与规模证据。不在本轮自动撰写完整投稿论文或承诺录用。']
    (ROOT/'docs/NEXT_VALIDATION_PLAN.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print('NEXT_PLAN_ONLY_WRITTEN',flush=True)
if __name__=='__main__':main()
