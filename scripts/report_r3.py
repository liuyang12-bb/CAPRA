"""Report and static scientific figures from sealed CSV/JSON only. No simulations."""
import csv,json,math,time
from pathlib import Path
from r3_utils import *
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
OUT=RUN/'analysis';FIG=RUN/'figures'
def f(x,n=2):return '—' if x is None else f'{x:.{n}f}'
def mdtable(headers,rows):
    return '|'+ '|'.join(headers)+'|\n|'+ '|'.join('---' for x in headers)+'|\n'+'\n'.join('|'+ '|'.join(str(v) for v in r)+'|' for r in rows)+'\n'
def main():
    began=time.perf_counter();freeze=load(RUN/'freeze_receipt.json') if (RUN/'freeze_receipt.json').exists() else None;FIG.mkdir(exist_ok=True);rows=load(OUT/'results.json');comps=load(OUT/'comparisons.json');metrics={m['id']:m for m in load(OUT/'metrics.json')};sources=load(OUT/'source_index.json')
    # Scientific figures consume the actual analysis CSV; nested worst-case ledgers
    # stay in JSON, with all plotted numerical columns checked against that index.
    number_fields=('mean_jct','p50_jct','p95_jct','p99_jct','makespan','mean_waiting','mean_training','mean_recovery','decision_median','decision_p95','decision_max','wall_seconds')
    rawrows=list(csv.DictReader((OUT/'results.csv').open(encoding='utf8',newline='')))
    assert len(rawrows)==len(rows)
    for x,y in zip(rawrows,rows):
        assert x['id']==y['id']
        for k in number_fields:
            x[k]=float(x[k]) if x[k] else None
            assert x[k]==y[k]
        for k in ('completed','total','censored','decision_gt5_count'):x[k]=int(x[k])
    rows=rawrows
    rawcomps=list(csv.DictReader((OUT/'comparisons.csv').open(encoding='utf8',newline='')))
    assert len(rawcomps)==len(comps)
    merged=[]
    for x,y in zip(rawcomps,comps):
        assert all(x[k]==str(y[k]) for k in ('comparison','phase','scenario','method','baseline'))
        for k in x:
            if isinstance(y.get(k),(int,float)):
                x[k]=float(x[k]) if x[k] else None
                assert x[k]==y[k]
                if isinstance(y[k],int):x[k]=int(x[k])
        merged.append(dict(y,**x))
    comps=merged
    physical=load(RUN/'results.json') if (RUN/'results.json').exists() else [];complete=sum(x['status']=='ALL_COMPLETE' and x.get('audit')=='PASS' for x in physical);aliases=load(RUN/'logical_reuse_results.json') if (RUN/'logical_reuse_results.json').exists() else []
    font=Path('C:/Windows/Fonts/msyh.ttc')
    if font.exists():font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(font)).get_name()
    plt.rcParams['axes.unicode_minus']=False;plt.rcParams['pdf.fonttype']=42
    saved=[]
    def save(fig,name):
        fig.savefig(FIG/(name+'.png'),dpi=180,bbox_inches='tight');fig.savefig(FIG/(name+'.pdf'),bbox_inches='tight');plt.close(fig);saved.append(name)
    # A: actual smart plus version-labelled history, no invented repair reruns.
    groups=('w2_dense_original','w6_dense_original','w2_dense_cm');methods=('SIA-P','SIA-P-K','SIA-SMART-P','CAPRA-FK','CAPRA')
    if any(r['phase']=='A' and r['result_origin']=='NEW_EXECUTION' for r in rows):
        fig,axes=plt.subplots(1,3,figsize=(15,4.4))
        for ax,scenario in zip(axes,groups):
            rs={r['method']:r for r in rows if r['phase']=='A' and r['scenario']==scenario};vals=[rs[m]['mean_jct'] if m in rs else np.nan for m in methods]
            bars=ax.bar(range(5),vals,color=['#98a4b3','#6f93b7','#2f5480','#e4ab55','#6d9e7d'])
            for b,v in zip(bars,vals):
                if math.isfinite(v):ax.text(b.get_x()+b.get_width()/2,v,f(v,0),ha='center',va='bottom',fontsize=9)
            ax.set_xticks(range(5),['Fast P','P-K','Smart P','FK','FKR']);ax.set_title(scenario);ax.set_ylabel('平均JCT（秒）');ax.set_ylim(0,max([v for v in vals if math.isfinite(v)]+[1])*1.2)
        fig.suptitle('A：补齐smart基线；W2/W6 original的FK/FKR为历史legacy，CM为R2修复版',fontsize=12);fig.tight_layout();save(fig,'A_smart_baseline')
    bgr=[w+'_'+p for w in ('saturn7_supported80','saturn8_supported80') for p in ('original','cm')]
    if any(r['phase']=='B' for r in rows):
        fig,axes=plt.subplots(1,4,figsize=(17,4.8));bm=('SIA-SMART-P','SIA-P-K','CAPRA-FK','CAPRA')
        for ax,sc in zip(axes,bgr):
            rs={r['method']:r for r in rows if r['phase']=='B' and r['scenario']==sc};vals=[rs[m]['mean_jct'] if m in rs else np.nan for m in bm]
            bars=ax.bar(range(4),vals,color=['#2f5480','#6f93b7','#e4ab55','#6d9e7d'])
            for b,m,v in zip(bars,bm,vals):
                if not math.isfinite(v):continue
                if rs[m]['result_origin']=='EQUIVALENCE_REUSED':b.set_edgecolor('black');b.set_linewidth(.6);b.set_hatch('///')
                ax.text(b.get_x()+b.get_width()/2,v,f(v,0)+(' *' if rs[m]['result_origin']=='EQUIVALENCE_REUSED' else ''),ha='center',va='bottom',fontsize=9)
            ax.set_xticks(range(4),['Smart P','P-K','FK','FKR']);ax.set_title(sc.replace('_supported80',''),fontsize=10);ax.set_ylabel('平均JCT（秒）');ax.set_ylim(0,max([v for v in vals if math.isfinite(v)]+[1])*1.2)
        fig.suptitle('B：未参与当前开发的Saturn7/8；*斜线=严格等价复用，非新增CM执行',fontsize=12);fig.tight_layout();save(fig,'B_holdout_four_methods')
    rc=[c for c in comps if c['phase']=='B' and c['method']=='CAPRA' and c['baseline']=='CAPRA-FK']
    if rc:
        fig,axes=plt.subplots(1,3,figsize=(15,4.8));labels=[c['scenario'].replace('_supported80','').replace('_','\n') for c in rc];x=np.arange(len(rc));mean=[c['mean_jct_improvement_percent'] for c in rc]
        axes[0].bar(x,mean,color=['#6d9e7d' if v>=0 else '#bb6c65' for v in mean]);axes[0].axhline(0,color='black',linewidth=.7);axes[0].set_ylabel('平均JCT改善（%）');axes[0].set_title('FKR相对FK：正值更快')
        axes[1].bar(x-.17,[c['decision_p95_baseline'] for c in rc],.34,label='FK',color='#e4ab55');axes[1].bar(x+.17,[c['decision_p95_method'] for c in rc],.34,label='FKR',color='#6d9e7d');axes[1].set_ylabel('非空完整决策P95（秒）');axes[1].legend();axes[1].set_title('控制开销，计时不进入模拟JCT')
        axes[2].bar(x,[c['ratio_max'] for c in rc],color='#a77c9b');axes[2].axhline(1,color='black',linewidth=.7);axes[2].set_ylabel('最差单作业JCT比值（FKR/FK）');axes[2].set_title('个体退化必须保留')
        for ax in axes:ax.set_xticks(x,labels,fontsize=9)
        fig.tight_layout();save(fig,'R_increment_overhead_tail')
    improvements=[c['mean_jct_improvement_percent'] for c in rc];wins=sum(v>0 for v in improvements)
    if complete==15 and len(aliases)==4 and len(rc)==4:
        if wins>=3 and np.mean(improvements)>0:recommend='建议下一轮以FK+ram_slack_v1为简洁主版本，保留冻结FKR作扩展强对照。R在四条件的平均JCT增量为+2.46%、+0.17%、+0.24%、−1.44%；三个条件增量很小或为负，Saturn7 original的P99还退化1.70%，而每个条件控制开销都增加。R2开发场景CM的9.21%未在这两条未使用负载中稳定延续；这不证明R无价值，也不自动删除R或加入新门控。当前控制耗时绝对值仍小，不能称不可用或过大。'
        elif wins<=1 or np.mean(improvements)<=0:recommend='建议以FK+ram_slack_v1作为更简单的主候选，保留FKR作特定场景对照；本轮不删R、不改H、不新增门控或重选数据。'
        else:recommend='先保留FK与FKR两个冻结版本；两个负载/画像间证据混合，下一步优先解释R的机会、个体退化和开销，再决定主版本。'
    else:recommend='证据尚未完整，暂不据不完整矩阵决定FK/FKR主版本；先解决明确停止原因，不自动扩预算或正式重试。'
    dump(OUT/'recommendation.json',dict(recommendation=recommend,R_comparisons=len(rc),R_mean_positive_conditions=wins,R_mean_improvement_percent=improvements,algorithm_changed_after_results=False))
    text=['# CAPRA R3：smart基线与未使用负载验证结果','',f'唯一基准 `{BASE}`；分支 `capra/smart-holdout-r3`，工作副本 `D:/科研启航/CAPRA-smart-holdout-r3`。新增物理正式完成 **{complete}/15**，通过审计的完整新增作业 **{sum(x.get("completed") or 0 for x in physical if x["status"]=="ALL_COMPLETE")}/1200**，严格等价逻辑复用 **{len(aliases)}/4**。历史引用另列，不算新增执行或独立样本。','',recommend,'','## A：smart补齐后的基线变化','', 'SIA-SMART-P是仓库内Sia smart placement在当前单节点、物理恢复锁和比例辅助资源模型下的适配基线，不等同官方完整系统。仅修正原smart排序引用jobname→x，保持稳定平局；有符号容量防护、空零规范和记录不改有效非空决策。GPU MIP/输入/配置/费用/锁保持；每个活动轮一次GPU MIP，无fast/K或辅助优化fallback。','']
    text += [mdtable(['场景','方法','身份/分配器','完成/删失','mean','P50','P95','P99','makespan'],[[r['scenario'],r['method'],r['result_origin']+'/'+r['allocator_mode'],str(r['completed'])+'/'+str(r['total'])+'; '+str(r['censored']),*[f(r[k]) for k in ('mean_jct','p50_jct','p95_jct','p99_jct','makespan')]] for r in rows if r['phase']=='A'])]
    if (RUN/'smart_control_certificate.json').exists():
        c=load(RUN/'smart_control_certificate.json');text += [f'W2 original/CM smart完整语义控制：**{c["status"]}**，{c["rounds"]}轮，逐作业CSV字节一致；逐轮分配/位置、候选、锁、batch、费用、执行分段与进度严格一致，排除项见证书。']
    else:text+=['W2 original/CM smart完整语义控制：尚无通过证据；复用门槛未满足。']
    text += ['',mdtable(['场景','比较','mean改善%','P95改善%','P99改善%','版本说明'],[[c['scenario'],c['method']+'/'+c['baseline'],*[f(c[k+'_improvement_percent']) for k in ('mean_jct','p95_jct','p99_jct')],'FK/FKR按源legacy/repair，不改标签'] for c in comps if c['phase']=='A'])]
    if 'A_smart_baseline' in saved:text += ['![A基线](../runs/smart_holdout_r3/figures/A_smart_baseline.png)']
    text += ['','## B：Saturn7/8泛化主比较','', '筛选与R2预登记源行号/hash一致：支持四应用、原请求GPU1..8、按原time再源行号取80，全部原字段和到达保留。Saturn7：71CIFAR/5DS/4BERT，225–22771秒；Saturn8：71CIFAR/8DS/1BERT，90–22529秒。未压缩到达、未按性能选数据。两个同Saturn来源族负载，称未参与当前开发的负载验证；不是跨多来源生产验证。original/CM为冻结受控响应，跨环境改变多项响应，非严格RAM单因素消融。','']
    text += [mdtable(['场景','方法','身份','完成/删失','mean','P50','P95','P99','makespan'],[[r['scenario'],r['method'],r['result_origin'],str(r['completed'])+'/'+str(r['total'])+'; '+str(r['censored']),*[f(r[k]) for k in ('mean_jct','p50_jct','p95_jct','p99_jct','makespan')]] for r in rows if r['phase']=='B'])]
    text += [mdtable(['场景','比较','mean改善%','P95改善%','P99改善%','makespan改善%'],[[c['scenario'],c['method']+'/'+c['baseline'],*[f(c[k+'_improvement_percent']) for k in ('mean_jct','p95_jct','p99_jct','makespan')]] for c in comps if c['phase']=='B'])]
    text += ['改善率=100×(1−method/baseline)，正为更快。全部比较在同画像下；比例方法allocator none是其合同，FK/FKR统一ram_slack_v1。CM比例逻辑格仅通过严格比例点/代码依赖/归纳证明/R2控制/A控制/源完整审计后复用，不复制原始日志；wall与组件计时只引用源original观测。条件资源诊断按目标CM重新只读计算，不冒充新执行。']
    if 'B_holdout_four_methods' in saved:text+=['![B四方法](../runs/smart_holdout_r3/figures/B_holdout_four_methods.png)']
    text += ['','## 尾部、个体退化与时间账本','',mdtable(['场景','比较','快/平/慢','比值P95/max','最差比值作业','增加秒','Δ等待/训练/恢复'],[[c['scenario'],c['method']+'/'+c['baseline'],f'{c["fast"]}/{c["tie"]}/{c["slow"]}',f'{f(c["ratio_p95"],3)}/{f(c["ratio_max"],3)}',c['worst_ratio_case']['job'],f(c['worst_ratio_case']['delta_jct']),'/'.join(f(c['mean_'+k+'_difference']) for k in ('waiting','training','recovery'))] for c in comps])]
    worst=max(comps,key=lambda c:c['worst_ratio_case']['relative_baseline_jct_ratio']) if comps else None
    if worst:
        for label,case in [('最大相对退化',max((c['worst_ratio_case'] for c in comps),key=lambda x:x['relative_baseline_jct_ratio'])),('最大绝对退化',max((c['worst_absolute_case'] for c in comps),key=lambda x:x['delta_jct']))]:
            text += [f'{label}：{case["scenario"]}，{case["method"]}/{case["baseline"]}，`{case["job"]}`，JCT {f(case["baseline_jct"])}→{f(case["method_jct"])}秒，比值{f(case["relative_baseline_jct_ratio"],3)}，增加{f(case["delta_jct"])}秒；等待/训练/恢复差为'+ '/'.join(f(case['method_'+k]-case['baseline_'+k]) for k in ('waiting','training','recovery'))+'秒。']
    text += ['比值是相对基线同作业JCT，不是经典独占slowdown。mean改善不意味着makespan/吞吐同比改善。时间账本差不作严格组件因果归因。','',mdtable(['场景/方法/身份','平均等待','平均训练','平均恢复','三项和/mean'],[[r['scenario']+'/'+r['method']+'/'+r['result_origin'],*[f(r['mean_'+k]) for k in ('waiting','training','recovery')],f(sum(r['mean_'+k] for k in ('waiting','training','recovery')))+'/'+f(r['mean_jct'])] for r in rows])]
    text += ['','## 控制开销与smart修复','',mdtable(['场景/方法/身份','median/P95/max秒','>5秒','格wall秒','计时来源'],[[r['scenario']+'/'+r['method']+'/'+r['result_origin'],'/'.join(f(r[k],4) for k in ('decision_median','decision_p95','decision_max')),r['decision_gt5_count'],f(r['wall_seconds']),r['timing_scope']] for r in rows])]
    text += ['完整决策边界含GPU准备/MIP、参考映射、候选及commit。候选F/K/R含配额/身份稳定/评分，RAM与mapping/scoring嵌套其中，不能再相加或机械相减。smart计时为物理放置，包含在共同GPU阶段；历史缺失组件为不可得。全部轮/非空轮分别保存在metrics.json。','',mdtable(['场景/Smart身份','非空轮','原保留作业轮','驱逐事件','见证修复轮/比例','受影响作业轮'],[[m['source']['scenario']+'/'+m['source']['result_origin'],m['extra']['counts'].get('active_rounds',0),m['extra']['counts'].get('raw_retained_job_rounds',0),m['extra']['counts'].get('raw_evicted_job_events',0),str(m['extra']['counts'].get('shared_witness_repair_rounds',0))+'/'+f((m['extra']['repair_fraction_active'] or 0)*100)+'%',m['extra']['counts'].get('shared_witness_changed_job_rounds',0)] for m in metrics.values() if m['source']['method']=='SIA-SMART-P'])]
    text += ['共同物理见证修复不是smart原生能力，具体作业、raw/修复/身份交换逐轮索引见各格smart_timeline.json和原始事件。若修复频繁，结论仅适用于此锁适配基线，不能归功于原smart。']
    if 'R_increment_overhead_tail' in saved:text+=['![R收益开销退化](../runs/smart_holdout_r3/figures/R_increment_overhead_tail.png)']
    text += ['','## 机制、资源机会与每应用','',mdtable(['场景/方法/身份','训练加权rho','rho/rho_prop','超比例训练%','CPU正条件%','RAM正条件%','RAM接受步骤/实际选中更新','终局RAM机会轮'],[[m['source']['scenario']+'/'+m['source']['method']+'/'+m['source']['result_origin'],f(m['training'].get('rho'),4),f(m['training'].get('relative_rho'),4),f(100*m['training'].get('above_prop',0)),f(100*m['training'].get('cpu_positive',0)),f(100*m['training'].get('ram_positive',0)),str(m['ram'].get('ram_steps','不可得'))+'/'+str(m['ram'].get('selected_updates','不可得')),m['residual_ram_rounds']] for m in metrics.values()])]
    text += [mdtable(['场景/方法','F/K/R或P选择','可行','纯节点迁移','GPU配置变化','aux更新','实际恢复秒'],[[m['source']['scenario']+'/'+m['source']['method']+'/'+m['source']['result_origin'],m['candidate_selected'],m['candidate_feasible'],m['pure_node_migrations'],m['other_gpu_configuration_changes'],m['transitions'].get('aux_update',0),f(m['actual_recovery'])] for m in metrics.values()])]
    text += [mdtable(['场景/方法/身份','应用','作业数','mean JCT'],[[m['source']['scenario']+'/'+m['source']['method']+'/'+m['source']['result_origin'],app,v['jobs'],f(v['mean_jct'])] for m in metrics.values() for app,v in m['application_results'].items()])]
    text += ['条件CPU/RAM差、资源正增益份额与训练加权rho是实际执行诊断，不能相加当总JCT收益。资源占用积分包含恢复，不称硬件忙碌利用率。F/K/R的Phi、未扣恢复sum-rho及R选择次数不转化为最终贡献百分比。节点终局RAM检查固定其他作业、CPU/GPU/位置，机会归零不代表全局最优。','', '全部组件时序、RAM实际更新点/训练份额、原始和稳定布局、同选/同类型/可同机/锁/参考已同机漏斗、各应用训练与GPU时间份额详见analysis/metrics.json及analysis/cells；它们不代表独立样本或严格因果分解。','', '## 研究判断与范围','',recommend]
    for scenario in groups:
        cs=[c for c in comps if c['phase']=='A' and c['scenario']==scenario]
        sm=next((c for c in cs if c['method']=='SIA-SMART-P' and c['baseline']=='SIA-P'),None)
        cap=next((c for c in cs if c['method']=='CAPRA' and c['baseline']=='SIA-SMART-P'),None)
        if sm and cap:text += [f'{scenario}：smart相对fast P平均改善{f(sm["mean_jct_improvement_percent"])}%；该场景有来源标签的CAPRA相对smart仍改善{f(cap["mean_jct_improvement_percent"])}%。这是两个完整策略对照，不把百分比相减/相除当严格机制贡献。']
    for c in rc:text += [f'{c["scenario"]}：R的FKR/FK平均增量{f(c["mean_jct_improvement_percent"])}%，P95/P99 {f(c["p95_jct_improvement_percent"])}/{f(c["p99_jct_improvement_percent"])}%，完整决策P95 {f(c["decision_p95_baseline"],4)}→{f(c["decision_p95_method"],4)}秒，个体最差比值{f(c["ratio_max"],3)}。']
    if complete==15 and len(aliases)==4:
        text += ['资源优化相对两个稳定比例基线，在四个负载/画像条件的平均JCT均有正收益；但Saturn7 original的FK/FKR相对smart的P95均退化2.88%，FKR的P99退化0.85%。因此支持的是均值改善及明确的适用边界，不能宣称每个尾部或每个任务都受益。',
        'R的额外机会有限：FKR在Saturn7 original/CM分别只选R 2/3轮，Saturn8 original/CM为7/6轮。CM下，存在同类型且GPU总和能同机的RAM互补任务的轮次，Saturn7为16轮、Saturn8为12轮；存在参考布局已将RAM互补任务同机的轮次分别12/11。上述是轮级“存在某对”标志，会重叠，不能用两个数相减当剩余机会数。它说明不少可组合资源机会已由参考布局覆盖，不能把R收益小归结为数据不合法，也不能据此重选输入。',
        'Saturn8 CM的FKR相对FK平均等待差0、训练差+2.8625秒、恢复差+8.4375秒，合计mean JCT+11.3秒；训练加权rho从FK的1.26763降到FKR的1.25410。最差配对任务cifar10-84从648到852秒，增加204秒（训练+54、恢复+150、等待不变），比值1.3148。以上是动态时间账本，不能当严格组件因果拆分。',
        'smart共同见证修复在A/W2 original、W2 CM、W6 original分别2/178、2/178、1/196个非空轮；holdout Saturn7为1/344，Saturn8为0/350。未出现大量由共同见证替换布局的情况，但基线仍是明确的恢复锁适配版本。',
        '本轮可支持：冻结模型下CPU/RAM配额与稳定布局结合，在两条未参与开发的同来源负载中保留均值收益；补齐smart后资源方法仍有增量。不能支持：R普遍必需、全体尾部/个体无退化、跨真实画像/多来源生产负载/规模普遍优越。下一步优先外部资源感知强基线及独立可追溯画像/误差验证；本轮只交计划，不自动展开。']
    text += ['本轮不要求获胜；没有结果后调H、删R、门控、改画像/负载、参数搜索、追加种子/正式重试。辅助响应沿用公开模板迁移及冻结合成敏感度假设，不当作真实CPU/RAM硬件实测。当前仅40GPU/每类型两节点、单节点数据并行；外部资源基线、画像误差、恢复费鲁棒性和规模待补。扩容仅静态审查与下一轮方案，见CAPRA_R3_SCALE_PLAN.md。','', '## 版本、预算、证据与调用','']
    budget=load(RUN/'budget_ledger.json');end=next((e for e in reversed(budget['entries']) if e['kind']=='budget_end'),None);elapsed=(end or {}).get('elapsed_seconds',budget.get('elapsed_seconds'))
    text += [f'统一预算使用{f(elapsed/60 if elapsed else None)} /120分钟，单调时钟deadline未重置。首次测试前启动，覆盖验证、固定状态、两次冒烟、输入、冻结、正式模拟、逐格独立审计、写盘和所属树清理。原测试内部18次Job.step单列；全部实际调用见simulation_calls.json，失败/NOT_RUN见根results和matrix_receipt。准备修正如有保留各次日志。纯离线报告时间另见delivery_clock.json；不启动新模拟。']
    if freeze:text += [f'第一格前同时冻结源码包 `{freeze["source_snapshot_sha256"]}`，{freeze["frozen_files"]}文件；保护基准{freeze["protected_files"]}文件。源码包不含声称覆盖自身hash的manifest，manifest指包，start指manifest；所有新/历史/逻辑复用证据有source_index。']
    text += ['本地交付，不自动推送。提交号由最终回复提供。手动推送：`git -C "D:/科研启航/CAPRA-smart-holdout-r3" push -u origin capra/smart-holdout-r3`。','', '核心文件：R3_README.md、docs/CAPRA_R3_BASELINE_SPEC.md、docs/CAPRA_R3_DESIGN.md、docs/CAPRA_R3_SMART.patch、data/holdout_r3、configs/experiment_manifest_{smart,holdout}_r3.json、runs/smart_holdout_r3/{source_snapshot.zip,results.csv,logical_reuse_results.json,analysis,figures,evidence_hashes.json,final_verification.json}。']
    (ROOT/'docs/CAPRA_R3_RESULTS.md').write_bytes(('\n\n'.join(text)+'\n').encode('utf8'))
    dump(OUT/'report_receipt.json',dict(status='PASS',wall_seconds=time.perf_counter()-began,figures=saved,simulator_calls=0,source_csv_sha256=sha(OUT/'results.csv'),comparisons_csv_sha256=sha(OUT/'comparisons.csv') if (OUT/'comparisons.csv').exists() else None))
    print('R3_REPORT_WRITTEN',flush=True)
if __name__=='__main__':main()
