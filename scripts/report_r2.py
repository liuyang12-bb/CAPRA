"""Tables and three PNG/PDF figures from independent R2 CSV/JSON analysis."""
import csv,math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from r2_utils import *
OUT=RUN/'analysis'
def fmt(x,n=2):return '不可得' if x is None else f'{x:.{n}f}'
def triple(x):return '不可得' if not x else '/'.join(fmt(x[k],4) for k in ('median','p95','max'))
def main():
    with (OUT/'stage_A.csv').open(encoding='utf8') as f:a_rows=list(csv.DictReader(f))
    with (OUT/'stage_B.csv').open(encoding='utf8') as f:b_rows=list(csv.DictReader(f))
    metrics=load(OUT/'metrics.json');lookup={m['id']:m for m in metrics};comparisons=load(OUT/'comparisons.json');matrix=load(RUN/'matrix_receipt.json');formal=load(RUN/'results.json');freeze=load(RUN/'freeze_receipt.json')
    def at(phase,scenario,method):return lookup.get(f'{phase}/{scenario}/{method}')
    def mean(phase,scenario,method):
        x=at(phase,scenario,method);return x['summary']['mean_jct'] if x else None
    scenarios=['w2_dense_original','w6_dense_original','w2_dense_cm'];methods=['SIA-P','SIA-P-K','CAPRA-Fixed','CAPRA-FK','CAPRA'];short=['SIA-P','P-K','Fixed','FK','FKR'];colors=['#828990','#b1b8be','#51a5bd','#387da1','#df893c']
    figdir=RUN/'figures';figdir.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size':10,'axes.spines.right':False,'axes.spines.top':False,'pdf.fonttype':42})
    def save(fig,name):
        for ext in ('png','pdf'):fig.savefig(figdir/f'{name}.{ext}',dpi=180)
        plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(14,4.8));fig.subplots_adjust(left=.06,right=.99,bottom=.20,top=.80,wspace=.29)
    for ax,scenario in zip(axes,scenarios):
        ys=[mean('A' if method in ('SIA-P-K','CAPRA-FK') else 'R1',scenario,method) for method in methods]
        if all(v is not None for v in ys):
            bars=ax.bar(short,ys,color=colors);ax.bar_label(bars,fmt='%.1f',fontsize=8,padding=3);ax.set_ylim(0,max(ys)*1.18)
        else:ax.text(.5,.5,'Incomplete evidence',transform=ax.transAxes,ha='center')
        ax.set_title(scenario);ax.set_ylabel('Mean JCT (simulated s)');ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    fig.suptitle('Phase A: placement retention, matched resource optimization, and R',y=.97,fontsize=14)
    fig.text(.5,.04,'P-K = SIA-P-K; FK = CAPRA-FK; FKR = CAPRA. SIA-P / Fixed / FKR reused from frozen R1.',ha='center',fontsize=9)
    save(fig,'A_five_methods')
    fig,axes=plt.subplots(1,2,figsize=(13,5.4));fig.subplots_adjust(left=.07,right=.99,bottom=.24,top=.82,wspace=.30)
    scenario='w2_dense_cm';bm=['CAPRA-Fixed','CAPRA-FK','CAPRA'];labels=['Fixed','FK','FKR'];legacy=['R1','A','R1'];x=np.arange(3);width=.34
    before=[mean(p,scenario,m) for p,m in zip(legacy,bm)];after=[mean('B',scenario,m) for m in bm]
    if all(v is not None for v in before+after):
        b1=axes[0].bar(x-width/2,before,width,label='Legacy allocator',color='#98a5ad');b2=axes[0].bar(x+width/2,after,width,label='RAM repair',color='#387da1')
        axes[0].bar_label(b1,fmt='%.1f',padding=3,fontsize=8);axes[0].bar_label(b2,fmt='%.1f',padding=3,fontsize=8);axes[0].set_ylim(0,max(before+after)*1.2)
    axes[0].set_xticks(x,labels);axes[0].set_ylabel('Mean JCT (simulated s)');axes[0].set_title('Each method before / after RAM repair')
    six=[at(p,scenario,m) for m,p in zip(bm,legacy) for p in (p,'B')];sixlabels=[s+' '+v for s in labels for v in ('old','new')]
    bottom=np.zeros(6)
    for field,color,label in [('mean_training','#51a5bd','Training'),('mean_recovery','#df893c','Recovery'),('mean_waiting','#b1b8be','Waiting')]:
        ys=np.array([m['summary'].get(field,0) if m else 0 for m in six]);axes[1].bar(sixlabels,ys,bottom=bottom,color=color,label=label);bottom+=ys
    axes[1].tick_params(axis='x',labelrotation=25);axes[1].set_title('Actual time accounting');axes[1].set_ylabel('Mean time per job (s)')
    for ax in axes:ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    h1,l1=axes[0].get_legend_handles_labels();h2,l2=axes[1].get_legend_handles_labels();fig.legend(h1+h2,l1+l2,loc='lower center',bbox_to_anchor=(.5,.01),ncol=5,frameon=False)
    fig.suptitle('Phase B / CM: bounded RAM supplement, identical method-wise comparisons',y=.98,fontsize=14)
    save(fig,'CM_ram_before_after')
    fig,axes=plt.subplots(1,2,figsize=(13,5));fig.subplots_adjust(left=.07,right=.99,bottom=.22,top=.80,wspace=.3)
    cases=[('A',s) for s in scenarios]+[('B','w2_dense_cm')];case_labels=['W2 old','W6 old','CM old','CM repaired'];gains=[];fkcost=[];fkrcost=[]
    for phase,s in cases:
        fk=at(phase,s,'CAPRA-FK');fkr=at('B' if phase=='B' else 'R1',s,'CAPRA')
        gains.append(100*(1-fkr['summary']['mean_jct']/fk['summary']['mean_jct']) if fk and fkr else np.nan)
        fkcost.append(fk['summary']['decision_p95'] if fk else np.nan);fkrcost.append(fkr['summary']['decision_p95'] if fkr else np.nan)
    bars=axes[0].bar(case_labels,gains,color=['#df893c' if x>=0 else '#b75a56' for x in gains]);axes[0].bar_label(bars,fmt='%.2f%%',padding=3);axes[0].axhline(0,color='#777',linewidth=.8)
    finite=[x for x in gains if np.isfinite(x)]
    if finite:axes[0].set_ylim(min(0,min(finite))-1.2,max(0,max(finite))+1.5)
    axes[0].set_ylabel('FKR mean JCT improvement over FK (%)');axes[0].set_title('Positive = FKR faster; negative = FK faster')
    xs=np.arange(4);axes[1].bar(xs-.18,fkcost,.36,label='FK',color='#387da1');axes[1].bar(xs+.18,fkrcost,.36,label='FKR',color='#df893c');axes[1].set_xticks(xs,case_labels);axes[1].set_ylabel('P95 complete decision time (s)');axes[1].set_title('Non-empty decisions; same locked numeric environment');axes[1].legend(frameon=False)
    for ax in axes:ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    fig.suptitle('R dynamic increment versus decision overhead',y=.97,fontsize=15)
    fig.text(.5,.035,'Legacy FKR timings are frozen R1 observations; missing old component timings are not reconstructed.',ha='center',fontsize=9)
    save(fig,'R_increment_overhead')
    lines=['# CAPRA R2：机制消融与RAM剩余容量修复结果','',
        f"唯一基准 `{BASE}`；分支 `capra/ablation-ram-r2`；工作副本 `D:/科研启航/CAPRA-ablation-ram-r2`。正式完成{sum(r['status']=='ALL_COMPLETE' for r in formal)}/9格，新增作业完成{sum(r.get('completed') or 0 for r in formal)}/720。旧R1的18格/1440次执行为历史，其中本轮分析只读复用三个场景的9格/720次，绝不计为新增样本。",'',
        '本轮先实现并同时冻结A/B，再顺序运行A六格和B三格。关闭修复时旧方法语义由54个固定状态回放证明；原33项测试通过，全部288条旧RAM证书按完整实际节点分为151组，顺序修复后终局无合法正增益。仅两次12作业30轮冒烟（未完成整体JCT为空），内部18次测试Job.step也有登记。','',
        '## 来源与公平边界','',
        '旧SIA-P/Fixed/完整CAPRA来自提交81b1109中的CAPRA_V2_SCENARIOS_R1；A新增SIA-P-K和FK用原比例/legacy分配；B的Fixed/FK/CAPRA同用ram_slack_v1。B前后FK旧值来自A第6格，其余旧值来自R1。SIA-P与SIA-P-K未在B重跑。source_index.json/csv记录每格来源、版本、路径、哈希和新/复用身份。',
        '', 'GPU阶段、上游、execution、identity、costs、response、node_allocator、旧placement/runner/audit、输入与历史全部原字节保护。新入口为runner_r2/placement_r2/audit_r2/audit_ram_r2，RAM仅包装原节点最终解。输入/40GPU/6节点/恢复费/H180/60秒周期/seed0/数值线程1不变，neutral=false。Python3.10.10、NumPy1.26.4、SciPy1.13.1、CVXPY1.6.5，HiGHS包装器二进制与R1环境哈希相同。','',
        '改善率=100×(1−method/baseline)，正为更快。两次动态运行时间差只称时间账本，不是严格组件因果。相对基线JCT比值不是相对于独占时间的经典slowdown。单个固定种子和派生场景不构成独立随机重复，不制造显著性。','',
        '## A：三个场景五方法','', '|场景|方法|来源|完成/状态|mean|P50|P95|P99|makespan|','|---|---|---|---|---:|---:|---:|---:|---:|']
    for row in a_rows:
        m=lookup[row['id']];s=m['summary'];lines.append('|'+ '|'.join([row['scenario'],row['method'],'R1复用' if row['reused']=='True' else 'A新增',f"{s['completed']}/{s['total']} {s['status']}"]+[fmt(s[k]) for k in ('mean_jct','p50_jct','p95_jct','p99_jct','makespan')])+'|')
    lines+=['','|场景|仅位置 P-K/P|优化下位置 FK/Fixed|对齐位置资源 FK/P-K|R增量 FKR/FK|','|---|---:|---:|---:|---:|']
    keys=['position_proportional','position_optimized','resource_matched_stability','R_dynamic_increment']
    for s in scenarios:
        values=[next((c['mean_jct_improvement_percent'] for c in comparisons if c['phase']=='A' and c['scenario']==s and c['comparison']==key),None) for key in keys]
        lines.append('|'+ '|'.join([s]+[fmt(v)+'%' for v in values])+'|')
    lines+=['','![A五方法](../runs/ablation_ram_r2/figures/A_five_methods.png)','',
        '## B：CM三方法RAM修复前后','', '|方法|分配器|来源|完成|mean|P95|P99|等待|训练|恢复|','|---|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for row in b_rows:
        s=lookup[row['id']]['summary'];lines.append('|'+ '|'.join([row['method'],row['allocator_mode'],row['phase'],str(s['completed'])]+[fmt(s[k]) for k in ('mean_jct','p95_jct','p99_jct','mean_waiting','mean_training','mean_recovery')])+'|')
    lines+=['','修复前后及同修复版本的比较见comparisons.csv/json；不将修复后的CAPRA对未修复Fixed当作公平方法增量。背景比例方法沿用A/R1并明确未在B执行。','',
        '![CM RAM修复前后](../runs/ablation_ram_r2/figures/CM_ram_before_after.png)','',
        '## 全部预定比较与逐作业退化','', '|阶段/场景|比较|mean改善%|P95改善%|P99改善%|快/平/慢|比值P95/max|最大比值作业|','|---|---|---:|---:|---:|---|---|---|']
    for c in comparisons:
        worst=c['worst_ratio_case'];lines.append('|'+ '|'.join([c['phase']+'/'+c['scenario'],c['method']+'/'+c['baseline']]+[fmt(c[k+'_improvement_percent']) for k in ('mean_jct','p95_jct','p99_jct')]+[f"{c['fast']}/{c['tie']}/{c['slow']}",fmt(c['ratio_p95'],3)+'/'+fmt(c['ratio_max'],3),worst['job'] if worst else '不可得'])+'|')
    lines+=['','全体逐作业正负差异见paired_jobs.csv；worst_cases.json同时保留最大比值和最大绝对JCT退化的任务及等待/训练/恢复。比值分母为该基线方法同任务JCT，不能称经典独占slowdown。','',
        '## 实际时间账本分解','', '|阶段/场景|比较|Δ等待|Δ训练|Δ恢复|三项合计|','|---|---|---:|---:|---:|---:|']
    for c in comparisons:
        d=[c['mean_'+p+'_difference'] for p in ('waiting','training','recovery')];lines.append('|'+ '|'.join([c['phase']+'/'+c['scenario'],c['method']+'/'+c['baseline']]+[fmt(x) for x in d]+[fmt(sum(d) if all(x is not None for x in d) else None)])+'|')
    lines+=['','## 每应用结果','', '|来源/场景/方法|应用|作业数|平均JCT|','|---|---|---:|---:|']
    for m in metrics:
        for app,s in m['application_results'].items():lines.append(f"|{m['id']}|{app}|{s['jobs']}|{fmt(s['mean_jct'])}|")
    lines+=['','## 响应与RAM实际执行指标','',
        '全部由实际训练段加权。rho_prop按本节点比例CPU/RAM计算；CPU条件差=rho(c,m)−rho(c_prop,m)，RAM条件差=rho(c,m)−rho(c,m_prop)，两者不能相加解释总收益或换算JCT。','',
        '|来源/场景/方法|rho|rho/rho_prop|超比例训练%|CPU条件差|CPU正训练%|RAM条件差|RAM正训练%|','|---|---:|---:|---:|---:|---:|---:|---:|']
    for m in metrics:
        t=m['training'];lines.append('|'+ '|'.join([m['id'],fmt(t.get('rho'),4),fmt(t.get('relative_rho'),4),fmt(100*t.get('above_prop',0)),fmt(t.get('cpu_conditional'),5),fmt(100*t.get('cpu_positive',0)),fmt(t.get('ram_conditional'),5),fmt(100*t.get('ram_positive',0))])+'|')
    lines+=['','|修复版方法|全部试算RAM调用/步骤/候选|最终选中更新|本轮补充影响训练%|非轴RAM训练%|训练加权额外GB|剩余机会轮|','|---|---|---:|---:|---:|---:|---:|']
    for method in bm:
        m=at('B','w2_dense_cm',method)
        if not m:continue
        t=m['training'];rr=m['ram'];lines.append('|'+ '|'.join([method,f"{rr.get('ram_calls',0)}/{rr.get('ram_steps',0)}/{rr.get('ram_candidates',0)}",str(rr.get('selected_updates',0)),fmt(100*t.get('ram_extra_this_round_training',0)),fmt(100*t.get('intermediate_ram_training',0)),fmt(t.get('extra_ram_gb',0)),str(m['residual_ram_rounds'])])+'|')
    lines+=['','“本轮补充影响训练”只计算当轮选择候选中相对旧最终节点解额外加RAM的任务；当前向量可能保留前轮新增中间点，所以非轴RAM训练份额另列。额外GB是对同轮旧节点最终解的差，不是跨运行硬件使用差。全部试算包含未选择R部分布局，不当作实际训练。各步原始证据在selection.allocator.ram_traces；分析目录ram_training_points.csv记录实际配额。',
        '', '终局机会直接检查固定CPU/位置、其他任务不变时的真实RAM上界，不使用旧pool_ram作为修复后的判据。残余证书逐个成立，不能累加共享空闲RAM的假想收益；旧288条验证分151组完整节点顺序执行，151次接受更新，无终局合法正增益。','',
        '## F/K/R、恢复与计时','', '|来源/场景/方法|非空轮|选择|可行|纯节点迁移|其他GPU配置变动|aux更新|实际恢复总秒|R调用|','|---|---:|---|---|---:|---:|---:|---:|---:|']
    for m in metrics:lines.append('|'+ '|'.join([m['id'],str(m['active_rounds']),str(m['candidate_selected']),str(m['candidate_feasible']),str(m['pure_node_migrations']),str(m['other_gpu_configuration_changes']),str(m['transitions'].get('aux_update',0)),fmt(m['actual_recovery']),str(m['r_calls_active']) if m['r_calls_active'] is not None else '旧日志不可得'])+'|')
    lines+=['','K不可行原因及Phi/未扣恢复sum-rho相对F分布在metrics.json和各格candidate_scores.csv。局部Phi与rho、K/R选择频次是机制描述，不直接换算动态贡献百分比。','',
        '|来源/场景/方法|原节点solve调用/命中|原候选对/升级|RAM请求/修复缓存命中|RAM步骤/总界|','|---|---|---|---|---|']
    for m in metrics:
        rr=m['ram'];lines.append('|'+ '|'.join([m['id'],f"{rr.get('legacy_node_calls',0)}/{rr.get('legacy_node_cache_hits',0)}",f"{rr.get('legacy_generated_pairs',0)}/{rr.get('legacy_upgrades',0)}",f"{rr.get('ram_requests',0)}/{rr.get('ram_cache_hits',0)}" if not m['source']['reused'] else '旧版本无RAM补充',f"{rr.get('ram_steps',0)}/{rr.get('ram_step_bound',0)}" if m['source']['allocator_mode']=='ram_slack_v1' else '不适用'])+'|')
    lines+=['','修复包装器在其缓存命中时不重新调用原solve，因此原缓存命中和包装器命中分层列出。RAM步骤总界是独立节点调用的上限之和；每次实际节点步骤均有单独有限性审计，不靠总和掩盖单节点越界。','',
        '|来源/场景/方法|完整决策median/P95/max|>5秒数/比例|格wall|F median/P95/max|K median/P95/max|R median/P95/max|RAM nested median/P95/max|','|---|---|---|---:|---|---|---|---|']
    for m in metrics:
        t=m['timing'];d=t['decision'];count=f"{d['gt5_count']}/{100*d['gt5_fraction']:.2f}%" if d else '不可得';lines.append('|'+ '|'.join([m['id'],triple(d),count,fmt(m['summary']['wall_seconds']),triple(t.get('F')),triple(t.get('K')),triple(t.get('R')),triple(t.get('ram_repair_nested'))])+'|')
    lines+=['','主开销只用非空轮，all_rounds独立保留。F/K/R组件计时含对应配额、稳定和评分；RAM及mapping/scoring嵌套在候选耗时内，不能重复加总或机械相减。R1缺失的组件计时均标不可得，不估造或补跑；同机不同批次wall为描述性观测，B完整CAPRA提供修复版R的实际组件时间。完整GPU准备/MIP→参考→候选→验证→提交的decision边界保持不变，不预设严格5秒上限。','',
        '![R增量与开销](../runs/ablation_ram_r2/figures/R_increment_overhead.png)','',
        '## 版本、预算及实际调用','',
        f"源码快照SHA256 `{freeze['source_snapshot_sha256']}`；A/B两份独立manifest SHA见freeze_receipt.json。源码包不包含manifest，manifest指源码包，start指manifest，避免自引用。冻结{freeze['frozen_files']}个文件；保护基准全部{freeze['protected_files']}个跟踪文件。",'',
        f"共享实验预算{matrix['elapsed_seconds']/60:.2f}/90分钟，起点为首次准备验证前，包含测试、回放、两次冒烟、环境失败、修正重验、冻结、A/B九格、逐格审计写盘及进程清理。阶段不重置，无正式自动重试。初步阅读/开发和矩阵后纯离线分析报告另记于最终delivery_clock。",'',
        '准备期曾因Python继承的Git命令配置COUNT缺少VALUE导致两次只读基准读取失败，未进入测试/模拟；保留preparation_01/02日志并仅修正该只读Git子进程的环境，未改全局Git配置。两次失败都在相同截止内。正式失败/未运行如有，完整保留root results和matrix_receipt，不将部分完成写成9/9。',
        '', '全部模拟调用索引将在simulation_calls.json汇总：原单元测试18次Job.step、两次短冒烟、至多9个正式进程，各有预算和所属树清理回执。使用挂起创建→分配Windows Job Object→恢复执行→清理全后代机制，只操作本轮自有进程。原18格只读，不运行旧准备/分析/封存入口。','',
        '## 研究判断','', '详见最终研究判断附件。','',
        '## 复现与交付入口','',
        '在本工作副本根目录，使用锁定环境（输出目录须为不存在的新目录）：','', '```powershell',
        '.\\.venv\\Scripts\\python.exe -X utf8 -B -m capra.runner_r2 --input data/scenarios_r1/w2_dense.csv --cluster data/scenarios_r1/cluster_cpu3.json --responses data/scenarios_r1/responses_cm.json --scenario-id w2_dense_cm --run-version CAPRA_V2_RAM_R2_REPRO --allocator-mode ram_slack_v1 --method CAPRA-FK --output runs/ablation_ram_r2/reproduction-new/CAPRA-FK --max-rounds 6000 --wall-limit 900',
        '.\\.venv\\Scripts\\python.exe -X utf8 -B -c "from capra.audit_r2 import audit; print(audit(\'runs/ablation_ram_r2/reproduction-new/CAPRA-FK\'))"',
        '.\\.venv\\Scripts\\python.exe -X utf8 -B scripts/analyze_r2.py',
        '.\\.venv\\Scripts\\python.exe -X utf8 -B scripts/report_r2.py',
        '```','',
        '新复现若需正式冻结身份，必须新目录、新预算与新manifest；上述REPRO是非正式单格接口演示，不能重用原已消耗的单调时钟截止。原九格由run_r2.py一次顺序执行，已有results时拒绝覆写。',
        '', '后续只读Saturn7/8来源核查与计划在docs/NEXT_VALIDATION_PLAN.md；本轮不生成该派生负载、不执行新矩阵。最终代码diff、证据hash、环境、调用索引和完整性核对在R2根目录/analysis。没有自动删除R或推送远端。']
    interpretation=ROOT/'docs/CAPRA_R2_INTERPRETATION.md'
    if interpretation.exists():lines=[x.replace('详见最终研究判断附件。',interpretation.read_text(encoding='utf8')) for x in lines]
    (ROOT/'docs/CAPRA_R2_RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print('R2_REPORT_AND_THREE_FIGURES_GENERATED',flush=True)
if __name__=='__main__':main()
