"""Rebuild portable CSV/JSON/PNG/SVG from existing evidence only; no simulation."""
from pathlib import Path
import argparse,sys,time,csv,math,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from capra.protocol_direct_eval_r6 import RUN,BASE,R4,load,dump,sha
from analyze_direct_eval_r6 import analyze
def fmt(x,d=2):return '—' if x is None else f'{x:.{d}f}'
def mdtable(head,rows):return '|'+ '|'.join(head)+'|\n|'+ '|'.join('---' for _ in head)+'|\n'+'\n'.join('|'+ '|'.join(str(v) for v in r)+'|' for r in rows)+'\n'
def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',default='configs/experiment_manifest_direct_eval_r6.json');p.add_argument('--output');p.add_argument('--budgeted',action='store_true');args=p.parse_args();began=time.monotonic()
    if args.budgeted:
        from budget_direct_eval_r6 import assert_window
        assert_window()
    manifest=Path(args.manifest);manifest=manifest if manifest.is_absolute() else ROOT/manifest
    initial=not (RUN/'analysis').exists();out=Path(args.output) if args.output else (RUN/'analysis' if initial else RUN/'analysis_rebuild'/f'rebuild_{time.time_ns()}')
    result=analyze(manifest,out);m=load(manifest);rows=result['results'];comparisons=result['comparisons'];mechanism=result['mechanism_summary'];metrics=result['metrics'];figdir=out/'figures';figdir.mkdir()
    # Every plotted value must roundtrip through the delivered results CSV.
    csvrows=list(csv.DictReader((out/'results.csv').open(encoding='utf8',newline='')));assert len(csvrows)==len(rows)
    for a,b in zip(rows,csvrows):
        for k in ('mean_jct','p95_jct','p99_jct'):
            if a[k] is None:assert not b[k]
            else:assert float(b[k])==a[k]
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    scenarios=list(dict.fromkeys(c['scenario'] for c in m['cells']));methods=['SIA-SMART-P','CAPRA-F-Only','CAPRA-Direct','CAPRA-FK','CAPRA'];labels=['Smart','F-only','Direct','FK','FKR'];colors=['#778899','#d99a3c','#3d8e71','#486fa1','#9273a7'];index={(r['scenario'],r['method']):r for r in rows}
    short=lambda s:s.replace('saturn','S').replace('_dense05_original','-O').replace('_dense05_cm','-CM')
    plt.rcParams.update({'font.size':10,'svg.fonttype':'none'});saved=[]
    def save(fig,name):
        fig.savefig(figdir/(name+'.png'),dpi=180,bbox_inches='tight');fig.savefig(figdir/(name+'.svg'),bbox_inches='tight');plt.close(fig);saved.append(name)
    fig,axes=plt.subplots(2,4,figsize=(19,8));x=np.arange(5)
    meanmax=max([r['mean_jct'] for r in rows if r['mean_jct'] is not None]+[1]);tailmax=max([r[k] for r in rows for k in ('p95_jct','p99_jct') if r[k] is not None]+[1])
    for col,s in enumerate(scenarios):
        rs=[index[s,method] for method in methods];mean=[r['mean_jct'] if r['mean_jct'] is not None else np.nan for r in rs]
        ax=axes[0,col];bars=ax.bar(x,mean,color=colors,edgecolor='black',linewidth=.3);ax.set_ylim(0,1.2*meanmax);ax.set_title(short(s));ax.set_ylabel('Mean JCT (s)')
        for b,v in zip(bars,mean):
            if math.isfinite(v):ax.text(b.get_x()+b.get_width()/2,v,fmt(v,0),ha='center',va='bottom',fontsize=9)
            else:ax.text(b.get_x()+b.get_width()/2,meanmax*.08,'NA',ha='center',color='gray')
        ax.set_xticks(x,labels,rotation=20,ha='right')
        ax=axes[1,col];p95=[r['p95_jct'] if r['p95_jct'] is not None else np.nan for r in rs];p99=[r['p99_jct'] if r['p99_jct'] is not None else np.nan for r in rs]
        ax.bar(x-.17,p95,.34,color=colors,edgecolor='black',linewidth=.3,label='P95');ax.bar(x+.17,p99,.34,color='white',edgecolor=colors,linewidth=1.2,label='P99');ax.set_ylim(0,1.25*tailmax);ax.set_ylabel('Tail JCT (s)');ax.set_xticks(x,labels,rotation=20,ha='right');ax.legend(loc='upper right',fontsize=8)
    fig.suptitle('Formal 80-job comparison: eligible R4 references + 8 independent R6 executions; NA = unavailable');fig.tight_layout();save(fig,'jct_and_tails')
    fig,axes=plt.subplots(2,2,figsize=(13,8));fields=['decision_median','decision_p95','decision_p99','decision_max'];ceiling=max([r[k] for r in rows if r['method'] in ('CAPRA-F-Only','CAPRA-Direct') for k in fields if r.get(k) is not None]+[.01])*1.22
    for ax,s in zip(axes.flat,scenarios):
        for i,(method,color) in enumerate([('CAPRA-F-Only',colors[1]),('CAPRA-Direct',colors[2])]):
            r=index[s,method];values=[r.get(k) if r.get(k) is not None else np.nan for k in fields];bars=ax.bar(np.arange(4)+(i-.5)*.36,values,.36,label=method,color=color,edgecolor='black',linewidth=.3)
            for b,v in zip(bars,values):
                if math.isfinite(v):ax.text(b.get_x()+b.get_width()/2,v,fmt(v,3),ha='center',va='bottom',fontsize=8)
        ax.set_xticks(range(4),['Median','P95','P99','Max']);ax.set_ylim(0,ceiling);ax.set_title(short(s));ax.set_ylabel('Full decision wall time (s)');ax.legend(fontsize=8)
    fig.suptitle('New R6 executions only; full GPU-to-commit decisions; wall time is not charged to simulated JCT');fig.tight_layout();save(fig,'decision_overhead')
    fig,axes=plt.subplots(2,2,figsize=(13,9));mr=[r for r in result['mechanism_rows'] if r.get('DeltaR') is not None];lim=max([abs(r[k]) for r in mr for k in ('DeltaR','DeltaL')]+[.1])*1.15
    for ax,s in zip(axes.flat,scenarios):
        subset=[r for r in mr if r['scenario']==s]
        for label,color in [('F','#929aa4'),('D','#23886a')]:
            rr=[r for r in subset if r['selected']==label];ax.scatter([r['DeltaR'] for r in rr],[r['DeltaL'] for r in rr],s=20,alpha=.65,color=color,label='Selected '+label)
        ax.plot([-lim,lim],[-lim,lim],color='#333333',linestyle='--',linewidth=.8,label='DeltaPhi = 0');ax.axhline(0,color='#aaaaaa',linewidth=.5);ax.axvline(0,color='#aaaaaa',linewidth=.5);ax.set_xlim(-lim,lim);ax.set_ylim(-lim,lim);ax.set_title(short(s)+f' (completed D rounds={len(subset)})');ax.set_xlabel('DeltaR: normalized sum-rho');ax.set_ylabel('DeltaL: rho-weighted recovery loss');ax.legend(fontsize=8)
        if not subset:ax.text(0,0,'No completed D evidence',ha='center')
    fig.suptitle('Same-state Direct-trajectory candidates: DeltaPhi = DeltaR - DeltaL; not end-to-end JCT contribution');fig.tight_layout();save(fig,'score_decomposition')
    primary=[c for c in comparisons if c['method']=='CAPRA-Direct' and c['baseline']=='CAPRA-F-Only'];valid=[c for c in primary if c['status']=='COMPARED'];complete_new=sum(r['result_origin']=='NEW_EXECUTION_R6' and r.get('execution_status')=='COMPLETE' and r['audit_status']=='PASS' for r in rows);eligible=sum(r['result_origin']=='REUSED_R4' and r.get('execution_status')=='COMPLETE' and r['audit_status']=='PASS' for r in rows)
    if complete_new<8:next_action='下一步只处理本轮明确的缺项或阻断原因，在新授权/预算下补齐有效正式证据；当前不据不完整矩阵改算法或宣布性能胜出。'
    elif any(c['mean_jct_improvement_percent']<0 or c['p99_jct_improvement_percent']<0 for c in comparisons if c['method']=='CAPRA-Direct' and c['status']=='COMPARED'):next_action='下一步优先对本轮已记录的候选Phi与闭环JCT/尾部不一致案例做有限、预注册的受控验证，检验恢复加权局部代理与后续GPU反馈的错配；先保留完整F-only保护和全部负结果，不直接扩大搜索或调整H。'
    else:next_action='下一步优先接入目标/资源/恢复模型匹配的Synergy-TUNE外部强基线；本轮内部增量成立仍不足以证明相对外部方法的优势。'
    source_sha=dict(results_csv=sha(out/'results.csv'),comparisons_csv=sha(out/'comparisons.csv'),mechanism_csv=sha(out/'mechanism_rounds.csv'))
    b=load(RUN/'budget_ledger.json');elapsed=time.monotonic()-b['start_monotonic'];remaining=max(0,min(b['deadline_monotonic']-time.monotonic(),b['deadline_epoch']-time.time()))
    body=['# CAPRA Direct R6：首批正式对照与机制分析','',f'有效新正式单元 **{complete_new}/8**；合格历史参照 **{eligible}/12**。R5算法基准`{BASE}`，R4来源`{R4}`，实际执行HEAD `{m["actual_execution_head"]}`。最终交付提交与执行HEAD分开报告。本轮不自动push。','', '## 方法、工程接入与冻结','', 'CAPRA-Direct正式决策直接调用原runner_direct_r5.decide，未复制或改写直接构造。CAPRA-F-Only只调用原DirectPlacement.prepare_f，以同一RepairAllocator形成完整F；spy验证未调用select/construct_d/can_finish/D_AFTER，D_status=NOT_APPLICABLE_F_ONLY，不算预算回退。两者从仿真起点独立初始化80作业、独立新进程闭环运行，每轮同一GpuStage一次、commit_v2一次；后续GPU序列允许随状态分化。Direct轨迹中的F不是F-only整条轨迹的反事实。','', 'R5全部旧受控文件保持原字节；GPU MIP、batch、在线模型、真实锁/费用、画像、H180、周期60、seed0、单线程及5秒协作式预算保持。新入口补足FORMAL、完整80行、不进展/控制开销停止、进程树硬限和可移植只读复核。R5的零费用fixture将全部transition costs（含迁移）清零，准确称零转换成本机制测试，不属于本轮真实恢复费用下的性能证据。','', '## 20格来源与完整结果','', 'NEW_EXECUTION_R6是本轮8格实际新运行；REUSED_R4只在逐格复用资格通过后进入比较。R4原版本、提交、目录、源码包、运行时间全部保留。Smart是冻结的Sia smart placement适配+比例配额，非官方完整系统原样复现；FK/FKR为原候选协议，F-only为优化辅助配额参考方案。方法自身定义差异不是核查失败。','', mdtable(['场景','方法','来源','执行/审计','提交/到达/完成','mean','median','P95','P99','makespan'],[[r['scenario'],r['display_method'],r['result_origin'],str(r.get('execution_status'))+'/'+str(r['audit_status']),'/'.join(str(r.get(k,0)) for k in ('submitted_count','arrived_count','completed_count')),*[fmt(r[k]) for k in ('mean_jct','median_jct','p95_jct','p99_jct','makespan')]] for r in rows]), '未完整80/80或审计未通过的总体JCT与makespan均留空，不用完成子集平均冒充总体。缺失/不合格原因在source_index.json与每格reuse_eligibility.json；未追加历史方法重跑。','', '## 同场景完整配对比较','', '改善率=100*(baseline-method)/baseline，正值表示更低耗时。相同作业ID/到达配对；F-only/Smart是参考放置+辅助配额优化系统的组合差异，不是只变CPU/RAM的严格单因素因果估计。','', mdtable(['场景','方法/基线','状态','mean改善%','P95改善%','P99改善%','快/平/慢','ratioP95/max'],[[c['scenario'],c['method']+'/'+('CAPRA-FKR' if c['baseline']=='CAPRA' else c['baseline']),c['status'],*[fmt(c.get(k+'_improvement_percent')) for k in ('mean_jct','p95_jct','p99_jct')],'/'.join(str(c.get(k,'—')) for k in ('fast','tie','slow')),fmt(c.get('ratio_p95'),3)+'/'+fmt(c.get('ratio_max'),3)] for c in comparisons]), '配对JCT比值不是独占运行slowdown；没有多seed或置信区间。两个trace的两种画像条件不是四条独立生产样本，640次提交也不是640个独立研究样本。调度轮不是统计独立样本。','', '![完整JCT与尾部](../'+str(figdir.relative_to(ROOT)).replace('\\','/')+'/jct_and_tails.png)','', '## 等待、训练、实际恢复与个体退化','', mdtable(['场景','方法/基线','平均等待差秒','平均训练差秒','平均实际恢复差秒','最差相对任务','最大绝对退化秒'],[[c['scenario'],c['method']+'/'+c['baseline'],*[fmt(c.get('mean_'+k+'_difference')) for k in ('waiting','training','recovery')],c.get('worst_ratio_job','—'),fmt(c.get('worst_absolute_delta'))] for c in comparisons if c['status']=='COMPARED']), '恢复汇总来自executions实际消耗，未把逐轮candidate.total_delay相加。逐方法首次start/resume、GPU类型/形状/组合变更、纯节点迁移（含batch合同一致）与aux-only更新分别记录于metrics.json。新费用总额与实际恢复消耗分开，跨轮remaining不重复当新费用。最大退化作业完整账本见worst_cases.json/paired_jobs.csv；预注册最大绝对退化案例含两条真实GPU/batch/配额/费用轨迹。整条轨迹差不是某单轮行动的严格因果效应。','', '## 精确机制：R、L与Phi','', '仅分析Direct轨迹完成D构造的非空轮：R=sum rho，L=sum rho*min(delay/180,1)，Phi=R-L，逐轮验证DeltaPhi=DeltaR-DeltaL。delay包含真实剩余恢复与本轮新增费用。sum rho是归一化画像收益之和，不是samples/s或JCT改善率。','']
    body += [mdtable(['场景','非空轮','选D/F','D完成','F严格Phi','F评分近似平局规则','最终平局同/异布局','预算回退'],[[x['scenario'],x['counts'].get('nonempty_rounds',0),str(x['counts'].get('selected_D',0))+'/'+str(x['counts'].get('selected_F',0)),x['counts'].get('D_COMPLETE',0),x['counts'].get('F_STRICT_PHI',0),x['counts'].get('F_DELAY_CHANGES_TIE_BREAK',0),str(x['counts'].get('F_FINAL_TIE_IDENTICAL_ALLOCATION',0))+'/'+str(x['counts'].get('F_FINAL_TIE_DIFFERENT_ALLOCATION',0)),x['counts'].get('budget_fallback',0)] for x in mechanism]), mdtable(['场景','raw rho增加','总delay减少','R/delay同但Phi异','raw增益被恢复抵消','Phi更高但场景JCT未改'],[[x['scenario'],*[x['counts'].get(k,0) for k in ('raw_sum_rho_up','total_delay_down','same_R_same_total_delay_Phi_diff','raw_rho_up_but_F_Phi_higher','D_Phi_higher_cohort_JCT_not_improved')]] for x in mechanism]), '上述标志可重叠，不能相加等于总数、相减推断遗漏；最后一列仅关联本场景整体JCT，不证明候选轮导致退化。未选D不等于没有任何理论优化机会；平局分完整Allocation相同与仅评分/费用相同，分层见mechanism_strata.csv。F-only的NOT_APPLICABLE不进入这些D回退计数。','', '![评分分解](../'+str(figdir.relative_to(ROOT)).replace('\\','/')+'/score_decomposition.png)','', '## CPU与RAM作用','', mdtable(['场景','CPU单变增益/损失任务轮','RAM单变增益/损失任务轮','联合变化增益/损失','变化但rho不变'],[[x['scenario'],str(x['counts'].get('quota_CPU_ONLY_GAIN',0))+'/'+str(x['counts'].get('quota_CPU_ONLY_LOSS',0)),str(x['counts'].get('quota_RAM_ONLY_GAIN',0))+'/'+str(x['counts'].get('quota_RAM_ONLY_LOSS',0)),str(x['counts'].get('quota_JOINT_CPU_RAM_GAIN',0))+'/'+str(x['counts'].get('quota_JOINT_CPU_RAM_LOSS',0)),x['counts'].get('quota_QUOTA_OR_NODE_CHANGE_NO_RHO_GAIN',0)] for x in mechanism]), 'CPU/RAM都变标联合变化，不拆成两者的JCT贡献百分比；只有配额变化而rho不变不记模型性能收益。共同分配器的实际训练加权RAM条件差在metrics.json/training_auxiliary_metrics；Direct额外放置的RAM单变/联合变化在quota_changes.csv，两者不混为一项。Original与CM是两种冻结组合响应条件，CM不是RAM单因素，也非真实硬件实测。','']
    if sum(x['counts'].get('quota_RAM_ONLY_GAIN',0) for x in mechanism)==0:body += ['本轮未观察到Direct相对同状态F的“CPU不变、仅RAM变化且rho增加”这一单独RAM增益；联合变化不据此拆分RAM贡献，也不修改画像再跑。']
    else:body += ['本轮观察到模型内RAM单独变化增益的任务轮，数量如表；这是同状态画像响应差，不等于独立RAM造成的端到端JCT贡献。']
    cases=load(out/'representative_cases.json')
    body += ['','## 预注册典型案例','']
    for case in cases:
        if case['status']=='ABSENT':body.append(case['scenario']+' / '+case['case']+'：没有符合预注册规则的案例。');continue
        if 'event' in case:
            r=case['event'];f,d=r['selection']['candidates'];rf,lf,pf=__import__('analyze_direct_eval_r6').score_parts(f);rd,ld,pd=__import__('analyze_direct_eval_r6').score_parts(d)
            body.append(f'{case["scenario"]} / {case["case"]}：轮{r["round"]}，选{r["selection"]["selected"]}，DeltaR={rd-rf:.6f}、DeltaL={ld-lf:.6f}、DeltaPhi={pd-pf:.6f}。GPU contract、完整节点/CPU/RAM/rho、真实锁与逐作业恢复费用完整保存在representative_cases.json。')
        else:
            j=case['paired_job'];body.append(f'{case["scenario"]} / 最大绝对退化：`{j["job"]}`，JCT {j["baseline_jct"]:.2f}→{j["method_jct"]:.2f}秒；等待/训练/恢复差{j["delta_waiting"]:.2f}/{j["delta_training"]:.2f}/{j["delta_recovery"]:.2f}秒。两个闭环的后续轨迹已保留，不归因于单轮D行动。')
    body += ['','## 开销与运行预算','', mdtable(['场景','方法','完整决策median/P95/P99/max秒','单元wall秒','原始独立审计秒'],[[r['scenario'],r['method'],'/'.join(fmt(r.get(k),5) for k in ('decision_median','decision_p95','decision_p99','decision_max')),fmt(r.get('unit_wall_seconds')),fmt(r.get('audit_seconds'))] for r in rows if r['result_origin']=='NEW_EXECUTION_R6']), '总轮与非空轮分别记录；开销表主分位数为非空轮，完整GPU-to-commit区间含必要F reference/配额/构造/比较/commit及未单列杂项。F reference、F quota、D、GPU、commit与嵌套completion/allocator/scoring边界在metrics.json明确，不把嵌套区间相加。R4旧wall仅历史参考，不计算跨测量环境的快几倍。真实wall不加入模拟JCT。','', '![新方法控制开销](../'+str(figdir.relative_to(ROOT)).replace('\\','/')+'/decision_overhead.png)', '',f'本报告生成时共享窗口已用{elapsed:.2f}/5400秒，剩余约{remaining:.2f}秒；最终以budget_ledger.json与final_verification.json为准。环境/定向验证合计<=300秒，历史资格核查<=120秒；每逻辑格所有attempt<=600秒、工作/审计<=570秒、清理预留30秒。每新格启动前要求至少600+180秒剩余。5秒候选协作预算、600秒单元硬限、90分钟全局窗口分别报告。最大观测wall低于周期也不构成硬实时保证。','', '## 下一步只建议一项','',next_action,'', '正确实现、完整运行、性能改善分别评价。下降、尾部退化、RAM增益未出现和不可比项全部保留。本轮未做新oracle/布局枚举/调参/额外训练；两个trace同源派生、固定seed、单节点与每GPU类型至多两节点范围限制仍在。','', '## 复现与证据入口','', f'运行源码包：`{m["source_snapshot"]}`，SHA256 `{m["source_snapshot_sha256"]}`；含GPU/训练性能CSV及传递源码，不只顶层Python。manifest与源码包没有自引用哈希循环。实际执行HEAD `{m["actual_execution_head"]}`，交付SHA由最后本地提交与回复提供。','', '- `DIRECT_EVAL_R6_README.md`：总入口。','- `configs/experiment_manifest_direct_eval_r6.json`：固定8格与全部来源/指标/停止合同。','- `runs/direct_eval_r6/matrix_ledger.json`、`budget_ledger.json`：所有单元/attempt/进程清理与实际wall。','- `historical_reuse/<scenario>/<method>/reuse_eligibility.json`：每格历史资格及原因。','- 本目录results/comparisons/paired_jobs/overhead/mechanism_rounds/quota_changes/representative_cases：表与案例。','', '在仓库根目录使用该环境（或匹配锁版本的新环境，PYTHONPATH指向当前src）：','', '```powershell','.\\.venv\\Scripts\\python.exe -X utf8 -B scripts/run_direct_eval_r6.py --manifest configs/experiment_manifest_direct_eval_r6.json --resume','.\\.venv\\Scripts\\python.exe -X utf8 -B scripts/verify_direct_eval_r6.py --manifest configs/experiment_manifest_direct_eval_r6.json','.\\.venv\\Scripts\\python.exe -X utf8 -B scripts/report_direct_eval_r6.py --manifest configs/experiment_manifest_direct_eval_r6.json','```','', 'verify/report不调用生产放置器、GPU MIP、Job.step，不枚举新布局；已有analysis时report写新analysis_rebuild目录，不覆盖封存原始数据。本轮自动复核/重建使用--budgeted并受原执行窗口约束，截止后不自动续算；用户以后显式手动只读复核是独立操作，不重置旧运行账本，也不启动新正式运行。','', '手动推送：`git -C "<本仓库路径>" push -u origin capra/direct-evaluation-r6`。本轮未推送。','']
    stage_rows=[]
    for ident,metric in result['metrics'].items():
        if metric['result_origin']!='NEW_EXECUTION_R6':continue
        for stage,values in metric['component_times'].items():
            if values:stage_rows.append(dict(scenario=metric['scenario'],method=metric['method'],stage=stage,**values))
    from analyze_direct_eval_r6 import table
    table(out/'stage_overhead.csv',stage_rows)
    budget_section=['预算状态采用Direct非空轮为分母，NOT_APPLICABLE_F_ONLY不计入：',mdtable(['场景','非空轮','D未开始预算退出','D中途预算退出','候选wall超过5秒','协作检查调用数'],[[x['scenario'],x['counts'].get('nonempty_rounds',0),x['counts'].get('D_D_NOT_STARTED_BUDGET',0),x['counts'].get('D_D_BUDGET',0),x['counts'].get('candidate_wall_above_5s',0),x['counts'].get('budget_check_calls',0)] for x in mechanism]),'GPU/F参考/F配额/D/commit及嵌套阶段各自median/P95/P99/max与样本数完整输出于stage_overhead.csv；inclusive嵌套阶段不相加。']
    pos=body.index('## 下一步只建议一项');body[pos:pos]=budget_section
    report=ROOT/'docs/CAPRA_DIRECT_R6_RESULTS.md' if initial else out/'CAPRA_DIRECT_R6_RESULTS.md';report.write_bytes(('\n\n'.join(body)+'\n').encode('utf8'))
    if initial:
        intro=['# CAPRA Direct R6 正式对照入口','',f'有效新正式运行{complete_new}/8，合格R4参照{eligible}/12；算法基准`{BASE}`，执行HEAD`{m["actual_execution_head"]}`。所有负结果保留；未推送。','', '- [中文结果报告](docs/CAPRA_DIRECT_R6_RESULTS.md)','- [设计与预登记](docs/CAPRA_DIRECT_R6_DESIGN.md)','- [冻结manifest](configs/experiment_manifest_direct_eval_r6.json)','- [正式单元与全部attempt](runs/direct_eval_r6/CAPRA_V2_DIRECT_EVAL_R6/)','- [矩阵ledger](runs/direct_eval_r6/matrix_ledger.json)','- [共享预算](runs/direct_eval_r6/budget_ledger.json)','- [R4复用资格](runs/direct_eval_r6/historical_reuse/)','- [结果、配对与机制表](runs/direct_eval_r6/analysis/)','- [最终核验](runs/direct_eval_r6/final_verification.json)','- [可移植复核脚本](scripts/verify_direct_eval_r6.py)','', '固定原始输入与R5算法字节保持。新verify/report只读封存证据，不调用生产调度器或训练；复核从当前ROOT解析相对路径，不要求旧磁盘路径或旧分支存在。','', '手动push：`git push -u origin capra/direct-evaluation-r6`。','']
        (ROOT/'DIRECT_EVAL_R6_README.md').write_bytes('\n'.join(intro).encode('utf8'))
    dump(out/'report_receipt.json',dict(status='PASS',wall_seconds=time.monotonic()-began,valid_new_cells=complete_new,eligible_R4=eligible,figures=saved,source_tables_sha256=source_sha,report=report.relative_to(ROOT).as_posix(),no_simulator_optimizer_or_layout_search=True,next_recommendation=next_action))
    print(json.dumps(dict(status='R6_REPORT_WRITTEN',complete_new=complete_new,eligible_R4=eligible,wall_seconds=time.monotonic()-began,output=out.relative_to(ROOT).as_posix())),flush=True)
if __name__=='__main__':main()
