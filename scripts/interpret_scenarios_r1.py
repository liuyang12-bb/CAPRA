"""Evidence-linked interpretations regenerated from the sealed matrix, no simulation."""
import csv,json
from pathlib import Path
def append_conclusions(root,out):
    load=lambda p:json.loads(p.read_text(encoding='utf8'))
    rs=load(out/'results.json');ms=load(out/'opportunity_summary.json');old=load(out/'original_v2_opportunity_reference.json')
    r={(x['scenario'],x['method']):x for x in rs};m={(x['scenario'],x['method']):x for x in ms}
    oldm={(x['workload'],x['method']):x for x in old}
    if len(rs)!=18 or not all(x['status']=='ALL_COMPLETE' for x in rs):return
    def improvement(a,b):return 100*(1-a/b)
    def number(x):return f'{x:.2f}'
    def pct(x):return f'{100*x:.2f}%'
    lines=['### 1. 到达密度：更拥挤没有增强辅助配额加速','']
    for w in (2,6):
        a=oldm[(w,'CAPRA')]['training_metrics'];b=m[(f'w{w}_dense_original','CAPRA')]['training_metrics']
        lines.append(f"W{w}的CAPRA训练加权rho由原场景{a['rho']:.4f}降到密集场景{b['rho']:.4f}，超过比例性能的训练份额由{pct(a['above_prop'])}降到{pct(b['above_prop'])}。所以本轮密度变化没有增加实际利用的配额加速。该比较受动态GPU轨迹及任务时间份额共同影响，不能单独估计物理机会总量。")
    lines+=['','密集场景CAPRA仍比同场景SIA-P/Fixed更快，需同时看恢复和训练时间。互补任务共同入选、同GPU类型和可装入同节点是不同条件；原画像的DS在比例点已饱和、BERT训练份额小。不能用“多数CIFAR单任务占满节点”解释本结果，也不能由同机闲置资源证书为零推断所有布局已最优。','',
        '### 2. CPU2/3/6：容量本身与重分配分开','']
    for s,label in [('w2_dense_cpu2','CPU2'),('w2_dense_original','CPU3'),('w2_dense_cpu6','CPU6')]:
        sia=r[(s,'SIA-P')];cap=r[(s,'CAPRA')];x=m[(s,'CAPRA')]['training_metrics']
        lines.append(f"{label}：SIA-P mean={sia['mean_jct']:.2f}，CAPRA mean={cap['mean_jct']:.2f}，同场景改善{improvement(cap['mean_jct'],sia['mean_jct']):.2f}%；CAPRA加权rho={x['rho']:.4f}，加权rho/rho_prop={x['relative']:.4f}，超比例训练份额={pct(x['above_prop'])}。")
    lines+=['','CPU6更快的基线首先反映容量本身；其rho不能直接与CPU2的rho比较后宣称调度收益。CPU6/Fixed mean=1037.025，比同场景SIA-P的1028.35慢约0.84%，表明瞬时比例性能保底不等于动态JCT保证。该负结果保持原样，没有重跑。','',
        '### 3. CN：持续CPU供给确实增加，F已覆盖相当一部分同机组合','']
    a=m[('w2_dense_original','CAPRA')]['training_metrics'];b=m[('w2_dense_cn','CAPRA')]['training_metrics'];cn=m[('w2_dense_cn','CAPRA')]
    lines.append(f"CAPRA实际低于比例CPU且不损比例rho的训练份额由原密集场景{pct(a['cpu_below_prop_no_loss_training'])}增到CN的{pct(b['cpu_below_prop_no_loss_training'])}；加权rho由{a['rho']:.4f}增到{b['rho']:.4f}，超过比例训练份额由{pct(a['above_prop'])}增到{pct(b['above_prop'])}。这证明CPU捐出更持续且部分转化为实际加速，但转换幅度远小于捐出训练份额增幅。")
    f=cn['funnel_rounds']
    lines.append(f"CN/CAPRA中，{f.get('cpu_complement_gpu_sum_fits',0)}个非空轮次存在同GPU类型且两任务GPU和可装入节点的CPU互补对；其中{f.get('cpu_complement_F_colocated',0)}轮F已至少同机放置一对，{f.get('all_compatible_pairs_already_F',0)}轮全部可组合的异类任务对已经在F同机。另有{f.get('cpu_complement_direct_move_blocked_gpu',0)}轮出现固定其他任务时直接迁移被目标节点GPU容量阻止的任务对。这些条件重叠，不能相加，也不表示全部机会被F用尽。")
    lines+=['','CPU/RAM donor角色定义为：在本场景比例点，至少存在一个更低的合法既有轴点可以保持比例rho，另一资源固定比例。它是画像能力；实际捐出份额另由真实配额计算。原画像→CN同时改变DS、CIFAR与BERT辅助响应，不是严格CPU单因素消融。','',
        '### 4. CM：新增RAM响应是否被实际利用','']
    for method in ('CAPRA-Fixed','CAPRA'):
        x=m[('w2_dense_cm',method)]['training_metrics'];a=r[('w2_dense_cn',method)];b=r[('w2_dense_cm',method)]
        lines.append(f"{method}：CM对CN平均JCT改善{improvement(b['mean_jct'],a['mean_jct']):.2f}%；实际RAM条件增益的训练时间加权均值={x['ram_difference']:.5f}，正RAM增益训练份额={pct(x['ram_positive'])}（CN均为0）。配额、画像和实际执行段共同支持“新增RAM机会被部分利用”，不是只看终局JCT。")
    lines+=['','CN/CM只改变DS的RAM响应，且SIA-P完整语义轨迹控制通过；可以检验这项输入因素的动态影响。CPU分配、GPU轨迹、恢复及任务份额仍可能随RAM响应共同演化，因此不能把条件增益数值直接换算成JCT的独立CPU/RAM因果份额。','',
        '### 5. 自由放置相对Fixed：实际时间账本','',
        '下表为CAPRA减Fixed，负数表示该时间项减少；三个差值之和等于mean JCT差。这是两次完整动态运行的实际时间账本，不是固定GPU轨迹的因果消融。','',
        '|场景|Δ等待|Δ训练|Δ恢复|Δmean JCT|选择F/K/R|','|---|---:|---:|---:|---:|---|']
    for s in dict.fromkeys(x['scenario'] for x in rs):
        a,b=r[(s,'CAPRA')],r[(s,'CAPRA-Fixed')];d=[a[k]-b[k] for k in ('mean_waiting','mean_training','mean_recovery')];assert abs(sum(d)-(a['mean_jct']-b['mean_jct']))<1e-6
        lines.append('|'+ '|'.join([s]+[number(v) for v in d]+[number(a['mean_jct']-b['mean_jct']),str(m[(s,'CAPRA')]['active_selected'])])+'|')
    lines+=['','每场景的R未扣恢复sum-rho增益与Phi增益另见sum_rho_minus_F、phi_minus_F；Phi高但sum-rho不高的R轮次，其同状态评分优势来自恢复延迟项。不能把这些预测节费相加当成最终JCT差，也不能把K/R选择次数当成训练加速次数。','',
        '### 6. RAM网格遗漏已经出现在动态正式轨迹','']
    certificates_index=[]
    for method in ('CAPRA-Fixed','CAPRA'):
        met=m[('w2_dense_cm',method)];cs=load(root/r[('w2_dense_cm',method)]['output']/'analysis_r1/slack_certificates.json');gaps=[c for c in cs if c['ram_candidate_gap']]
        lines.append(f"CM/{method}：{met['ram_candidate_gap_rounds']}个非空轮次有独立RAM漏点证书，涉及训练时间份额{pct(met['training_metrics']['ram_gap_training'])}。这些证书固定其他任务与位置，并排除决策时恢复锁，不是静态例推断。")
        if gaps:
            exact=next((c for c in gaps if abs(c['proposed_ram']-416.68)<1e-6),gaps[0])
            lines.append(f"实例：round {exact['round']}（t={exact['time']:.0f}），`{exact['job']}`在`{exact['node']}`用{exact['gpus']}GPU/{exact['cpu']:.2f}CPU/{exact['ram']:.2f}GB，rho={exact['rho']:.5f}，实际训练{exact['training_seconds']:.2f}秒。该节点当轮空闲RAM={exact['free_ram']:.2f}GB，保持CPU和其他任务不变，将目标RAM设为{exact['proposed_ram']:.2f}GB可得rho={exact['rho_ram_only']:.5f}；冻结候选RAM池为{exact['ram_pool']}，无任何当前可容纳的正增益候选点。")
            certificates_index.append(dict(scenario='w2_dense_cm',method=method,**exact))
    (out/'highlighted_ram_certificates.json').write_text(json.dumps(certificates_index,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    lines+=['','这是本轮已经证实的配额候选局限，不是整个放置空间全局最优差距的证明。同类型GPU数量、恢复锁和固定其他任务的容量约束也可限制机会；完整筛选分布及各轮证书保留在原始分析文件。不同目标可能共享空闲资源，禁止把单证书增益相加。','',
        '### 7. 均值与尾部','']
    bad=[]
    for s in dict.fromkeys(x['scenario'] for x in rs):
        a,b=r[(s,'CAPRA')],r[(s,'SIA-P')];g95=improvement(a['p95_jct'],b['p95_jct']);g99=improvement(a['p99_jct'],b['p99_jct'])
        lines.append(f"{s}：CAPRA对SIA-P的P95改善{g95:.2f}%、P99改善{g99:.2f}%；正数更快，负数为尾部退化。")
        if g95<0 or g99<0:bad.append(s)
    lines.append('本次CAPRA相对SIA-P存在尾部退化的场景：'+('、'.join(bad) if bad else '无')+'。这不撤销原v2 W2的尾部负结果，也不形成尾部性能保证。Fixed的负面结果及CAPRA对Fixed的各项尾部比较同样完整保留在comparisons.csv。')
    lines+=['','### 8. 可信结论与下一版最小方向','',
        '本轮支持：节点内重分配确实产生CPU及RAM训练增益；自由放置相对Fixed的增量需要同时核对训练和恢复，不能等同于纯资源吞吐收益；更多CPU或更密到达不必然扩大资源优化空间。F在许多实际可组合轮次已经同机放置至少一对互补任务，而恢复成本和同型GPU装箱限制仍然存在。',
        '', '本轮不能确定：三布局之外是否存在显著更优布局、当前GPU计划是否遗漏更大跨类型联合机会、每个启发式距离全局JCT最优多远。未运行oracle或新消融，不能自行宣称F/R已全局充分利用，也不能将剩余问题全归咎于测试数据。',
        '', '下一版最小且有证据的方向，是单独修复已证实的RAM剩余容量候选漏点，保持有限搜索边界，再另行登记同输入对照验证；本轮没有执行该修改、没有重调H、没有追加实验。合成敏感度的说服力仍限于受控仿真机制验证，真实画像与更广负载验证是后续独立问题。']
    path=root/'docs/SCENARIOS_R1_RESULTS.md';text=path.read_text(encoding='utf8');text=text.replace('下述结论在读取全部18格及原始机会证据后补充。','\n'.join(lines));path.write_text(text,encoding='utf8')
