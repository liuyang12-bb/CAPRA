"""Chinese research report and scientific plots from actual CSV; no simulation/search."""
from pathlib import Path
from collections import Counter
import csv,json,time,math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from r4_utils import *
OUT=RUN/'analysis';FIG=RUN/'figures'
def fmt(x,n=2):return '—' if x is None or x=='' else f'{float(x):.{n}f}'
def tab(head,rows):return '|'+ '|'.join(head)+'|\n|'+ '|'.join('---' for _ in head)+'|\n'+'\n'.join('|'+ '|'.join(str(v) for v in r)+'|' for r in rows)+'\n'
def csvrows(p):return list(csv.DictReader(Path(p).open(encoding='utf8',newline='')))
def main():
    began=time.perf_counter();FIG.mkdir(exist_ok=True);rows=csvrows(OUT/'results.csv');comps=load(OUT/'comparisons.json');ccsv=csvrows(OUT/'comparisons.csv');metrics={x['id']:x for x in load(OUT/'metrics.json')};funnel=csvrows(OUT/'opportunity_funnel.csv') if (OUT/'opportunity_funnel.csv').exists() else [];sensitivity=csvrows(OUT/'scenario_sensitivity.csv');physical=load(RUN/'results.json');freeze=load(RUN/'freeze_receipt.json') if (RUN/'freeze_receipt.json').exists() else None
    numeric=('mean_jct','p50_jct','p95_jct','p99_jct','makespan','mean_waiting','mean_training','mean_recovery','decision_median','decision_p95','decision_p99','decision_max','wall_seconds','audit_seconds','gpu_allocated_fraction','cpu_allocated_fraction','ram_allocated_fraction','average_active_jobs','average_queue_jobs','peak_queue')
    for r in rows:
        for k in numeric:r[k]=float(r[k]) if r[k] else None
        for k in ('completed','total','censored','decision_gt5_count'):r[k]=int(r[k])
        x=metrics[r['id']]['summary']
        for k in ('mean_jct','p50_jct','p95_jct','p99_jct','makespan'):assert r[k]==x[k]
    assert len(comps)==len(ccsv)
    for a,b in zip(comps,ccsv):
        assert all(str(a[k])==b[k] for k in ('scenario','method','baseline'))
        for k in ('mean_jct_improvement_percent','p95_jct_improvement_percent','p99_jct_improvement_percent'):assert float(b[k])==a[k]
    font=Path('C:/Windows/Fonts/msyh.ttc')
    if font.exists():font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(font)).get_name()
    plt.rcParams['axes.unicode_minus']=False;plt.rcParams['pdf.fonttype']=42
    scenarios=[f'saturn{w}_dense05_{p}' for w in (7,8) for p in ('original','cm')];methods=('SIA-SMART-P','CAPRA-FK','CAPRA');names={'SIA-SMART-P':'Smart','CAPRA-FK':'FK','CAPRA':'FKR'};palette={'SIA-SMART-P':'#375d82','CAPRA-FK':'#dfa54f','CAPRA':'#6c9d7b'};short=lambda s:s.replace('saturn','S').replace('_dense05_original','-O').replace('_dense05_cm','-CM');saved=[]
    def save(fig,name):
        fig.savefig(FIG/(name+'.png'),dpi=180,bbox_inches='tight');fig.savefig(FIG/(name+'.pdf'),bbox_inches='tight');plt.close(fig);saved.append(name)
    nr={(r['scenario'],r['method']):r for r in rows if r['phase']=='R4'}
    sr={(r['scenario'],r['method']):r for r in sensitivity}
    if nr and sr:
        fig,axes=plt.subplots(2,2,figsize=(16,9));cats=[(s,m) for s in scenarios for m in methods if (s,m) in sr];x=np.arange(len(cats));a,b=axes[0]
        a.bar(x-.18,[100*float(sr[s,m]['GLOBAL_gpus_R3']) for s,m in cats],.36,label='R3原到达',color='#adb6c2',edgecolor='black',linewidth=.3);a.bar(x+.18,[100*float(sr[s,m]['GLOBAL_gpus_R4']) for s,m in cats],.36,label='dense05',color='#3d6d90',edgecolor='black',linewidth=.3);a.set_xticks(x,[short(s)+'\n'+names[m] for s,m in cats],fontsize=8);a.set_ylabel('全局GPU分配容量时间占比（%）');a.set_title('同一算法，原始与增密场景');a.legend(fontsize=9)
        tc=[(s,t) for s in scenarios if (s,'CAPRA') in sr for t in ('aws','dgx-ext','rtx')];z=np.arange(len(tc))
        b.bar(z-.18,[100*float(sr[s,'CAPRA']['TYPE:'+t+'_gpus_R3']) for s,t in tc],.36,label='R3原到达',color='#adb6c2',edgecolor='black',linewidth=.3);b.bar(z+.18,[100*float(sr[s,'CAPRA']['TYPE:'+t+'_gpus_R4']) for s,t in tc],.36,label='dense05',color='#6c9d7b',edgecolor='black',linewidth=.3);b.set_xticks(z,[short(s)+'\n'+t for s,t in tc],fontsize=8);b.set_ylabel('该GPU类型分配容量时间占比（%）');b.set_title('FKR：不同GPU池的压力');b.legend(fontsize=9)
        for ax,field,title,ylabel in [(axes[1,0],'queue','FKR：平均等待队列','平均等待作业数'),(axes[1,1],'mean_jct','FKR：JCT场景敏感性','平均JCT（秒）')]:
            ss=[s for s in scenarios if (s,'CAPRA') in sr];xx=np.arange(len(ss));keya='queue_R3' if field=='queue' else 'R3_mean_jct';keyb='queue_R4' if field=='queue' else 'R4_mean_jct'
            ax.bar(xx-.18,[float(sr[s,'CAPRA'][keya]) for s in ss],.36,label='R3原到达',color='#adb6c2',edgecolor='black',linewidth=.3);ax.bar(xx+.18,[float(sr[s,'CAPRA'][keyb]) for s in ss],.36,label='dense05',color='#6c9d7b',edgecolor='black',linewidth=.3);ax.set_xticks(xx,[short(s) for s in ss]);ax.set_title(title);ax.set_ylabel(ylabel);ax.legend(fontsize=9)
        fig.suptitle('原始与dense05：场景敏感性，不是算法贡献；资源分配积分含恢复，不是物理忙碌率',fontsize=13);fig.tight_layout();save(fig,'pressure_before_after')
    if funnel:
        fig,axes=plt.subplots(2,2,figsize=(17,9));labels=['非空计划','互补同池','GPU可同机','F/K未共置','直接合法证书','R覆盖','sum-rho增益','扣费选R','真实正增益训练']
        for ax,s in zip(axes.flat,scenarios):
            vals={x['stage']:x for x in funnel if x['scenario']==s and x['method']=='CAPRA'}
            if not vals:ax.set_title(short(s)+'：证据不足');continue
            stages=list('ABCDEFGHI');n=int(vals['A']['denominator_nonempty_rounds']);counts=[int(vals[k]['numerator']) for k in stages];assert all(b<=a for a,b in zip(counts,counts[1:]));pct=[100*v/n if n else 0 for v in counts]
            bars=ax.bar(range(9),pct,color=['#3a6387']*5+['#6c9d7b']*4,edgecolor='black',linewidth=.3)
            for b,v in zip(bars,counts):ax.text(b.get_x()+b.get_width()/2,b.get_height()+1,str(v),ha='center',fontsize=9)
            ax.set_xticks(range(9),labels,rotation=30,ha='right',fontsize=9);ax.set_ylim(0,112);ax.set_ylabel('占同一分母N的轮次（%）');ax.set_title(short(s)+f'：N={n}，全部R选择={vals["A"]["total_R_selected"]}')
        fig.suptitle('严格嵌套的新共置机会漏斗（FKR）；R可因恢复加权窗口或平局规则在漏斗外入选',fontsize=13);fig.tight_layout();save(fig,'opportunity_funnel')
    if nr:
        fig,axes=plt.subplots(3,4,figsize=(18,10));x=np.arange(3)
        for col,s in enumerate(scenarios):
            rs=[nr.get((s,m)) for m in methods]
            for row,(field,title) in enumerate([('mean_jct','平均JCT（秒）'),('p95_jct','JCT尾部（秒）'),('decision_p95','非空决策P95（秒）')]):
                ax=axes[row,col];values=[r[field] if r else np.nan for r in rs]
                if row==1:
                    p99=[r['p99_jct'] if r else np.nan for r in rs];ax.bar(x-.17,values,.34,color=[palette[m] for m in methods],edgecolor='black',linewidth=.3,label='P95');ax.bar(x+.17,p99,.34,color=[palette[m] for m in methods],edgecolor='black',linewidth=.6,hatch='///',label='P99');ax.legend(fontsize=8)
                else:
                    bars=ax.bar(x,values,color=[palette[m] for m in methods],edgecolor='black',linewidth=.3)
                    for b,v in zip(bars,values):
                        if math.isfinite(v):ax.text(b.get_x()+b.get_width()/2,v,fmt(v,3 if row==2 else 0),ha='center',va='bottom',fontsize=9)
                    finite=[v for v in values if math.isfinite(v)];ax.set_ylim(0,max(finite+[.01])*1.2)
                ax.set_xticks(x,['Smart','FK','FKR']);ax.set_ylabel(title)
                if row==0:ax.set_title(short(s))
        fig.suptitle('dense05：相同画像内三方法主对照；JCT越低越好，决策wall不计入模拟JCT',fontsize=13);fig.tight_layout();save(fig,'main_jct_tail_cost')
    render_report(rows,comps,metrics,funnel,sensitivity,physical,freeze,saved)
    dump(OUT/'report_receipt.json',dict(status='PASS',wall_seconds=time.perf_counter()-began,figures=saved,CSV_results_sha256=sha(OUT/'results.csv'),CSV_comparisons_sha256=sha(OUT/'comparisons.csv'),simulation_calls=0,state_search_calls=0))
    print('R4_REPORT_WRITTEN')

def render_report(rows,comps,metrics,funnel,sensitivity,physical,freeze,saved):
    complete=sum(r.get('state')=='COMPLETE_PASS' for r in physical);rr=[c for c in comps if c['method']=='CAPRA' and c['baseline']=='CAPRA-FK'];fk=[c for c in comps if c['method']=='CAPRA-FK' and c['baseline']=='SIA-SMART-P'];reviews=load(OUT/'bounded_layout_reviews.json') if (OUT/'bounded_layout_reviews.json').exists() else [];diag=load(OUT/'diagnosis_receipt.json') if (OUT/'diagnosis_receipt.json').exists() else None
    missed=[x for x in reviews if x['positive_net_layout_missed_by_recorded_candidates']];wins=sum(c['mean_jct_improvement_percent']>0 for c in rr)
    if complete<12:recommend='暂时保持FK/FKR并行，不根据不完整矩阵收敛主方法；先处理明确的停止原因。'
    else:recommend='先保留FK与FKR并行；主方法取舍由完整固定对照、尾部、开销与有限诊断证据联合判断，不设必须达到某个收益百分比的成功门槛。'
    if complete==12 and missed:priority='优先1：对已给出正净Phi遗漏证书的R状态做针对性机理核验，另立语义版本再决定是否修正；优先2：公平接入Synergy-TUNE外部强基线；优先3：CPU/RAM画像误差与少量可追溯实测；优先4：按既有DP/identity方案独立验证80GPU/160作业扩容。遗漏证书仅局部静态评分，不保证修改后JCT改善。'
    else:priority='优先1：统一目标/资源约束/恢复执行模型的Synergy-TUNE外部强基线；优先2：CPU/RAM画像误差与少量可追溯实测；优先3：按R3规模计划验证80GPU/160作业扩容；优先4：R针对性改进，仅在更明确机会或预测偏差证据支持时单独立项。有限小状态未发现遗漏不证明R全局完备。'
    decision=OUT/'research_decision.json'
    if complete==12 and decision.exists():
        reviewed=load(decision);assert reviewed['results_csv_sha256']==sha(OUT/'results.csv') and reviewed['comparisons_csv_sha256']==sha(OUT/'comparisons.csv')
        recommend=reviewed['recommendation'];priority=reviewed['priority']
    judgment=dict(recommendation=recommend,priority=priority,complete_cells=complete,R_mean_improvements=[c['mean_jct_improvement_percent'] for c in rr],R_positive_conditions=wins,reviewed_small_states=len(reviews),missed_positive_net_states=len(missed),algorithm_changed_in_R4=False)
    dump(OUT/'research_judgment.json',judgment)
    body=['# CAPRA R4：冻结算法下的资源竞争压力与R机会诊断','',f'基准 `{BASE}`；独立分支 `capra/pressure-opportunity-r4`。正式完整{complete}/12格，完整新增作业{sum(r.get("completed",0) for r in physical if r.get("state")=="COMPLETE_PASS")}/960。R3原到达条件只标HISTORICAL_REFERENCE；本轮12格均要求独立实际运行，无比例等价复用。','',recommend,'','## 输入、算法与环境','', '只把原R3 supported80的时间改为Decimal精确`t0+(ti-t0)/2`：Saturn7首末225/11498秒，Saturn8为90/11309.5秒；其余字段、原行身份/顺序、应用、训练量和请求GPU不变。这是原holdout的压力派生场景，不是新独立holdout或真实生产记录。Original/CM沿用冻结哈希，为两种受控组合响应，非RAM单因素消融。','', 'R3 GPU MIP、goodput/在线模型与batch、物理锁、恢复费、commit、F/K/R、Phi/H180/EPS/平局、NodeAllocator及ram_slack_v1全部保持原源码；仅新增R4方法白名单/入口/独立审计及原样转发的只读计时代理。Smart仍是Sia smart placement单节点/锁/比例辅助资源适配基线，不称官方完整系统原样复现。FK真正不生成R。40GPU/6节点/三类型每型2节点，周期60秒、seed0、Python3.10.10/NumPy1.26.4/SciPy1.13.1/CVXPY1.6.5/原HiGHS二进制、数值线程1不变。','', '验证包括45项测试、R3固定状态回放和两次12作业30轮短闭环；首轮新增测试的非稳定身份夹具被原R3前置断言正确拒绝，修正夹具后复验通过，算法未改。首轮/复验、全部内部Job.step和进程清理单独留档；两次冒烟未完成整体指标为空。闭环对照直接与归档R3同输入smoke逐轮比较GPU计划/batch/配额/锁/费用/进度及逐作业CSV，不重跑R3。','', '## 12格主结果与配对比较','']
    if complete==12 and decision.exists():
        for answer in load(decision).get('answers',[]):body.append(answer)
    new=[r for r in rows if r['phase']=='R4']
    body += [tab(['场景','方法','submitted/完成/删失','mean','median','P95','P99','makespan'],[[r['scenario'],r['display_method'],f'{r["total"]}/{r["completed"]}/{r["censored"]}',*[fmt(r[k]) for k in ('mean_jct','p50_jct','p95_jct','p99_jct','makespan')]] for r in new])]
    body += [tab(['场景','比较','mean改善%','P95改善%','P99改善%','makespan改善%','快/平/慢','比值P95/max'],[[c['scenario'],c['method']+'/'+c['baseline'],*[fmt(c[k+'_improvement_percent']) for k in ('mean_jct','p95_jct','p99_jct','makespan')],f'{c["fast"]}/{c["tie"]}/{c["slow"]}',fmt(c['ratio_p95'],3)+'/'+fmt(c['ratio_max'],3)] for c in comps])]
    body += ['改善率100*(1-method/base)，正为更快。只比较同一dense05、同一画像；资源方法统一ram_slack_v1，Smart按合同为比例/none。比值是同任务相对基线JCT，不是独占slowdown；配对记录不是新增独立样本。不完整格留空全体统计，不拿完成子集平均冒充总体。','',tab(['场景/方法','平均等待','训练','恢复','三项和/mean'],[[r['scenario']+'/'+r['display_method'],*[fmt(r['mean_'+p]) for p in ('waiting','training','recovery')],fmt(sum(r['mean_'+p] for p in ('waiting','training','recovery')))+'/'+fmt(r['mean_jct'])] for r in new])]
    body += ['','## 原始到达与dense05的压力变化','', '压力用资源分配量的时间积分/窗口容量时间计算，包含恢复，不是GPU或CPU实际忙碌率。按每个运行最早到达至最后完成的共同窗口，对每节点/类型/全局输出GPU/CPU/RAM占比及GPU满容量、CPU/RAM>=95%容量的精确时长。平均活跃/等待/训练/恢复作业数由完整时间账本积分得出；峰值队列为决策时刻采样。未调度作业没有指定GPU池，等待队列不任意分摊到某GPU类型。','']
    body += [tab(['场景/方法','GPU原→密%','CPU原→密%','RAM原→密%','平均队列原→密','平均活跃原→密','mean原→密'],[[r['scenario']+'/'+r['method'],*[fmt(100*float(r['GLOBAL_'+p+'_R3']))+'→'+fmt(100*float(r['GLOBAL_'+p+'_R4'])) for p in ('gpus','cpu','ram')],fmt(r['queue_R3'],3)+'→'+fmt(r['queue_R4'],3),fmt(r['active_R3'],3)+'→'+fmt(r['active_R4'],3),fmt(r['R3_mean_jct'])+'→'+fmt(r['R4_mean_jct'])] for r in sensitivity])]
    body += [tab(['场景/方法','AWS GPU原→密%','DGX GPU原→密%','RTX GPU原→密%'],[[r['scenario']+'/'+r['method'],*[fmt(100*float(r['TYPE:'+t+'_gpus_R3']))+'→'+fmt(100*float(r['TYPE:'+t+'_gpus_R4'])) for t in ('aws','dgx-ext','rtx')]] for r in sensitivity])]
    body += [tab(['场景/方法','CPU分配>=95%容量时间%','RAM分配>=95%容量时间%','GPU形状限制辅助增益任务轮','仍有节点内rho潜力任务轮'],[[x['source']['scenario']+'/'+x['source']['method'],fmt(100*x['pressure']['global_resources']['cpu_high_capacity_time_fraction']),fmt(100*x['pressure']['global_resources']['ram_high_capacity_time_fraction']),x['pressure']['auxiliary_limits']['GPU_shape_caps_all_aux_gain_job_rounds'],x['pressure']['auxiliary_limits']['has_unrealized_within_node_rho_gain_job_rounds']] for x in metrics.values() if x['source']['phase']=='R4'])]
    body += ['冻结画像下，每个已选作业当前GPU形状的合法节点内preferred配额之和/容量，以及超过容量的决策占比，另见pressure_metrics.json。它是读表的需求压力指标，不是原trace的CPU/RAM请求、实际预留或可获正净收益证明；GPU形状限制标志也不证明应改变GPU配置，本轮GPU MIP保持冻结。全局CPU/RAM不满不能替代每节点/池局部瓶颈检查。']
    if sensitivity:
        growth={t:np.mean([float(r['TYPE:'+t+'_gpus_delta_percentage_points']) for r in sensitivity]) for t in ('aws','dgx-ext','rtx')};top=max(growth,key=growth.get)
        body += ['按所有同算法/同画像配对的描述性平均，GPU分配占比增幅最大池为'+top+'，各池增幅百分点为'+str({k:round(v,3) for k,v in growth.items()})+'。这是这些固定场景的描述，不制造显著性。']
    body += ['R3→dense05只表述场景敏感性，不算算法贡献。占比增加可能来自到达窗口缩短和排队/训练轨迹变化；更高GPU占用也可能减少辅助资源空闲，不能先验认定帮助R。若某GPU池或队列未增压，应保留该负结果，不现场换密度或筛作业。']
    if 'pressure_before_after' in saved:body += ['![压力前后](../runs/pressure_r4/figures/pressure_before_after.png)']
    body += ['','## 严格嵌套机会漏斗与非互斥标签','', '统一分母N为每格非空完整GPU计划轮次；逐轮0/1去重。A非空→B同型互补→C GPU和可同机→D未在任一可行F/K中共置→E完整直接搬移合法见证→F实际R覆盖→G gross sum-rho胜最佳F/K→H扣费后原规则选R→I当轮实际训练正辅助增益。每层是前层子集。Smart/FK按协议不生成R，F之后为0，不是“算法漏候选”。R也可能因rho加权恢复窗口、平局规则或在已共置布局调整配额而在该漏斗外入选，全部R选择另列。标签R_selected_cost_or_tie_only只表示选R且gross sum-rho未严格增加，不能据此断言原始迁移总费用下降。','']
    groups={}
    for x in funnel:groups.setdefault((x['scenario'],x['method']),{})[x['stage']]=x
    body += [tab(['场景/方法','N','A/B/C/D/E/F/G/H/I','全部R选择'],[[s+'/'+m,next(iter(v.values()))['denominator_nonempty_rounds'],'/'.join(v[k]['numerator'] for k in 'ABCDEFGHI'),next(iter(v.values()))['total_R_selected']] for (s,m),v in groups.items()])]
    body += ['D是“某对尚未被F/K任一候选共置”的保守定义；F/K分别覆盖不同任务对不等于某个单一布局同时覆盖所有组合。E是比例基线+精确锁下不改变第三作业位置的充分直接见证；失败不证明没有其他合法布局。这个漏斗不是R全部动作空间或全局正净收益机会的完备证明。不同GPU池/碎片/辅助容量/锁/已共置/未生成R/增益不足/费用抵消等标签会重叠，不能相减推断遗漏数量。每轮任务、资源、证书、gross/净Phi在opportunity_rounds.jsonl.gz，非互斥标签在各格opportunity_summary.json。']
    if 'opportunity_funnel' in saved:body += ['![机会漏斗](../runs/pressure_r4/figures/opportunity_funnel.png)']
    body += ['','## 有限覆盖审查、历史正负案例与动态结果','']
    if diag:body += [f'预算内诊断完成：{diag["small_states"]}个按预注册规则抽取的小状态、{diag["enumerated_layouts"]}个同型整布局，正净Phi优于记录F/K/R而遗漏的状态{diag["missed_positive_net_states"]}个。上限8状态、每状态总任务<=6/未锁<=4/最多16布局，总128布局；抽样列表在首次枚举前落盘。缺失类别不更换规则补满。节点配额、RAM补充、身份和评分仍用冻结R3算法，并独立核对容量/rho/评分。不是全局配额或全程JCT最优。']
    else:body += ['预算内机会诊断未完整完成，缺失证据不填充、不追加状态枚举。']
    body += [tab(['场景/轮','任务/未锁','已枚举/可行','最佳−FK Phi','最佳−记录最佳Phi','遗漏正净状态'],[[x['scenario']+'/'+str(x['round']),str(x['jobs'])+'/'+str(x['unlocked']),str(x['attempted_layouts'])+'/'+str(x['feasible_layouts']),fmt(x['best_over_FK_phi'],6),fmt(x['best_over_recorded_phi'],6),x['positive_net_layout_missed_by_recorded_candidates']] for x in reviews])]
    cases=load(OUT/'opportunity_cases.json') if (OUT/'opportunity_cases.json').exists() else []
    for c in cases:
        if 'job_id' not in c:continue
        a,b=c['actual_full_ledger'],c['actual_baseline_ledger'];pr=c.get('predicted_R') or {}
        body += [f'{c["result_origin"]} / {c["scenario"]} / {c["case"]}：任务`{c["job_id"]}`，R轮{c["R_round"]}，JCT {fmt(b["jct"])}→{fmt(a["jct"])}秒，比值{fmt(c["jct_ratio"],4)}；等待/训练/恢复差 '+ '/'.join(fmt(a[k]-b[k]) for k in ('waiting','training','recovery'))+'秒。R预测rho='+fmt((c.get('R_allocation') or {}).get('rho'),5)+'，预测新费用='+fmt(pr.get('new_cost'))+'秒；R/参考Phi '+fmt(c['R_phi'],6)+'/'+fmt(c['FK_phi'],6)+'。完整节点/配额、费用、后续GPU/batch重配与逐段实际训练/恢复见opportunity_cases.json。']
    body += ['R2 W2-CM正收益与R3 Saturn8-CM负收益仅从已有冻结原始日志读取，未重跑；源哈希、首次R代表轮及真实受影响任务可追溯。预测费用与实际commit/剩余恢复一致性由审计验证；若轨迹JCT变差，不能直接称迁移费计算错或rho预测错误。局部H180代理与未来GPU/完成/恢复反馈可不一致。所有案例的全程时间账本差都不是某单轮R行动的严格因果效果。','', '## 尾部、个体退化与资源实际收益','']
    body += [tab(['场景/比较','最差相对任务','基线→方法JCT','比值','最差绝对任务/增加秒'],[[c['scenario']+'/'+c['method']+'/'+c['baseline'],c['worst_ratio_case']['job'],fmt(c['worst_ratio_case']['baseline_jct'])+'→'+fmt(c['worst_ratio_case']['method_jct']),fmt(c['ratio_max'],4),c['worst_absolute_case']['job']+'/'+fmt(c['worst_absolute_case']['delta_jct'])] for c in comps])]
    body += [tab(['场景/方法','rho加权','超比例训练%','CPU正条件%','RAM正条件%','RAM更新/所选更新','残余单任务RAM机会轮'],[[x['source']['scenario']+'/'+x['source']['method'],fmt(x['training'].get('rho'),5),fmt(100*x['training'].get('above_prop',0)),fmt(100*x['training'].get('cpu_positive',0)),fmt(100*x['training'].get('ram_positive',0)),str(x['ram'].get('ram_steps','不可得'))+'/'+str(x['ram'].get('selected_updates','不可得')),x['residual_ram_rounds']] for x in metrics.values() if x['source']['phase']=='R4'])]
    body += ['CPU/RAM条件差不能相加当整体JCT贡献。残余RAM机会固定GPU/CPU/位置及其他作业；为零不等于全局最优。R选择次数或某轮Phi优势不换算成端到端贡献百分比。','', '## 控制开销、候选、迁移与审计','']
    body += [tab(['场景/方法','median/P95/P99/max秒','>5秒','整格wall秒','独立审计秒'],[[r['scenario']+'/'+r['display_method'],'/'.join(fmt(r[k],4) for k in ('decision_median','decision_p95','decision_p99','decision_max')),r['decision_gt5_count'],fmt(r['wall_seconds']),fmt(r['audit_seconds'])] for r in new])]
    body += [tab(['场景/方法','F/K/R/P选择','可行候选','纯节点迁移','GPU配置变化','aux更新','实际恢复秒'],[[x['source']['scenario']+'/'+x['source']['method'],x['candidate_selected'],x['candidate_feasible'],x['pure_node_migrations'],x['other_gpu_configuration_changes'],x['transitions'].get('aux_update',0),fmt(x['actual_recovery'])] for x in metrics.values() if x['source']['phase']=='R4'])]
    body += ['MIP组件使用原上游stdout setup/solve区间，逐次数量与事件调用对齐，精度0.01ms；不能对应时标不可得。共同GPU阶段包括MIP准备/求解和smart。identity/reference与mapping+scoring、节点分配器、R、RAM都是明确嵌套区间，不重复求和，也不从总量机械相减造缺失组件。每格完整组件median/P95/P99/max、all_rounds与非空轮分开保存于metrics.json/pressure_metrics.json；审计秒数为整格审计核心检查区间，最终序列化/写盘仍包含在整格wall中，均不进入模拟JCT。','']
    for x in metrics.values():
        if x['source']['phase']!='R4':continue
        body += [x['source']['scenario']+'/'+x['source']['method']+' 组件P95（秒）：'+str({k:round(v['p95'],6) for k,v in x['timing'].items() if v and k in ('gpu','reference','mapping_scoring_nested','allocator_inclusive_nested','R','ram_repair_nested')})+'；MIP='+fmt((x['pressure']['timings']['mip_total'] or {}).get('p95'),6)+'；候选失败='+str(x['candidate_failures'])+'。']
    if 'main_jct_tail_cost' in saved:body += ['![主结果与尾部开销](../runs/pressure_r4/figures/main_jct_tail_cost.png)']
    body += ['','## 每应用JCT','',tab(['场景/方法','应用','作业数','mean JCT'],[[x['source']['scenario']+'/'+x['source']['method'],app,v['jobs'],fmt(v['mean_jct'])] for x in metrics.values() if x['source']['phase']=='R4' for app,v in x['application_results'].items()]),'','## 下一阶段明确决定','',recommend,'',priority,'', '判断限制：只有两条同Saturn来源族负载及其压力/画像派生，不是大量独立工作负载；单个固定种子，不制造显著性。沿用的CPU/RAM模板转移和CM合成敏感度不是硬件实测。当前仅单节点作业、40GPU、每类型两节点。本轮不执行R5/R6，不以删除DP/identity两节点断言扩容。','', '## 冻结、预算、失败与证据','']
    budget=ledger();end=next(e for e in reversed(budget['entries']) if e['kind']=='budget_end')
    body += [f'统一单调预算{fmt(end["elapsed_seconds"]/60)}/180分钟，未重置。覆盖首轮失败、复验、固定状态、两次闭环、输入、冻结、12格、逐格审计、预算内有限诊断及所属树清理。前期实现与完全离线报告另计，见delivery_clock.json；后处理没有追加模拟或状态搜索。正式无自动重试，所有失败与NOT_RUN保留。']
    if freeze:body += [f'源码快照SHA256 `{freeze["source_snapshot_sha256"]}`，冻结{freeze["frozen_files"]}文件，保护基准{freeze["protected_files"]}文件。源码包不含其自身哈希清单或指向它的manifest循环；manifest指源码包，start指manifest。来源和结果hash、ledger各格CREATED/RUNNING/COMPLETE_PASS/FAIL/INCOMPLETE/NOT_RUN、实际调用清单与进程树清理见runs/pressure_r4。']
    body += ['完整表和原始证据入口：R4_README.md；results.csv仅本轮实际运行，analysis/results.csv及source_index明确历史参照；diagnostic_raw_integrity.json与raw_integrity.json只读保护证明；全部证据SHA见evidence_hashes.json。','', '本地独立提交，不自动推送。手动命令：`git -C "D:/科研启航/CAPRA-pressure-opportunity-r4" push -u origin capra/pressure-opportunity-r4`。']
    (ROOT/'docs/CAPRA_R4_RESULTS.md').write_bytes(('\n\n'.join(body)+'\n').encode('utf8'))
    plan=['# CAPRA R4 下一阶段决定（只建议，不实施）','',recommend,'',priority,'','## 本轮R增量','',tab(['条件','FKR/FK mean改善%','P95改善%','P99改善%'],[[x['scenario'],fmt(x['mean_jct_improvement_percent']),fmt(x['p95_jct_improvement_percent']),fmt(x['p99_jct_improvement_percent'])] for x in rr]),'','## 可验收的下一步边界','', 'R针对性任务：只针对可追溯遗漏/恢复反馈反例，另立版本并冻结有限验证，不在看结果后无限改H或调画像。局部Phi改进须重新验证动态JCT、尾部与个体。','', '80GPU/160作业：先独立验证多桶GPU可行性与多节点身份映射，不能删两节点断言；扩容同时匹配作业量/到达强度，沿用R3_SCALE_PLAN，不把轻负载硬扩容当可扩展性证据。','', 'Synergy-TUNE：先明确GPU/batch目标与CPU/RAM接口，统一容量、最低配额、恢复锁/费用、训练执行与JCT口径；外部基线的适配合同与独立审计先行。','', '画像误差/少量实测：冻结有限扰动与可追溯CPU/RAM测量方案，不按结果放大敏感度，不把合成模板当硬件数据。','', '以上R5/R6均未实施，未新增正式实验。']
    (ROOT/'docs/CAPRA_R4_NEXT_PLAN.md').write_bytes(('\n\n'.join(plan)+'\n').encode('utf8'))
if __name__=='__main__':main()
