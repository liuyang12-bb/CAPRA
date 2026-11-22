"""Report/figures from completed audited evidence; never runs a scheduler."""
from pathlib import Path
import csv,json,math,time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'runs/scenarios_r1/CAPRA_V2_SCENARIOS_R1'
def load(p):return json.loads(p.read_text(encoding='utf8'))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def table(p,rows):
    if rows:
        with p.open('w',newline='',encoding='utf8') as f:
            w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
def fmt(v,n=2):return '—' if v is None else f'{v:.{n}f}'
def gain(a,b):return None if a is None or b is None else 100*(1-a/b)
def main():
    results=load(OUT/'results.json');analyses=load(OUT/'opportunity_summary.json');control=load(OUT/'cn_cm_siap_control.json');manifest=load(ROOT/'configs/experiment_manifest_scenarios_r1.json');budget=load(ROOT/'runs/scenarios_r1/budget_ledger.json')
    scenarios=list(dict.fromkeys(r['scenario'] for r in results));methods=['SIA-P','CAPRA-Fixed','CAPRA'];lookup={(r['scenario'],r['method']):r for r in results};metrics={(m['scenario'],m['method']):m for m in analyses}
    comparisons=[]
    for s in scenarios:
        for method,baseline in (('CAPRA-Fixed','SIA-P'),('CAPRA','SIA-P'),('CAPRA','CAPRA-Fixed')):
            a,b=lookup[(s,method)],lookup[(s,baseline)];row=dict(scenario=s,method=method,baseline=baseline)
            for k in ('mean_jct','p95_jct','p99_jct','makespan','mean_recovery'):
                row[k+'_improvement_percent']=gain(a.get(k),b.get(k))
            for k in ('mean_waiting','mean_training','mean_recovery'):row[k+'_method_minus_baseline']=a.get(k,0)-b.get(k,0) if a.get(k) is not None and b.get(k) is not None else None
            comparisons.append(row)
    table(OUT/'comparisons.csv',comparisons);dump(OUT/'comparisons.json',comparisons)
    old=[]
    for w in (2,6):
        for method in methods:
            s=load(ROOT/f'runs/capra_v2/CAPRA_V2_R1/saturn-{w}-supported80/{method}/summary.json')
            old.append(dict(workload=f'original_w{w}',method=method,**{k:s[k] for k in ('mean_jct','p50_jct','p95_jct','p99_jct','makespan','mean_waiting','mean_training','mean_recovery')}))
    table(OUT/'original_v2_reference.csv',old)
    figs=OUT/'figures';figs.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
    colors=['#737b86','#50a6c2','#d68238'];labels=['SIA-P','CAPRA-Fixed','CAPRA']
    fig,axes=plt.subplots(2,3,figsize=(13,7.3),constrained_layout=True)
    for ax,s in zip(axes.flat,scenarios):
        ys=[lookup[(s,m)].get('mean_jct') for m in methods]
        if all(v is not None for v in ys):
            bars=ax.bar(labels,ys,color=colors,width=.64);ax.bar_label(bars,fmt='%.1f',padding=3,fontsize=9);ax.set_ylim(0,max(ys)*1.2)
        else:ax.text(.5,.5,'Incomplete / censored',transform=ax.transAxes,ha='center')
        ax.set_title(s);ax.set_ylabel('Mean JCT (simulated seconds)');ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    fig.suptitle('Frozen CAPRA v2: six controlled scenarios (80 jobs per cell)',fontsize=15)
    for ext in ('png','pdf'):fig.savefig(figs/f'mean_jct.{ext}',dpi=180)
    plt.close(fig)
    fig,axes=plt.subplots(2,3,figsize=(13,7.3))
    fig.subplots_adjust(left=.07,right=.99,bottom=.12,top=.89,hspace=.38,wspace=.32)
    for ax,s in zip(axes.flat,scenarios):
        bottom=np.zeros(3)
        for field,color,label in [('mean_training','#50a6c2','Training'),('mean_recovery','#d68238','Recovery'),('mean_waiting','#adb3bd','Waiting')]:
            ys=np.array([lookup[(s,m)].get(field) or 0 for m in methods]);ax.bar(labels,ys,bottom=bottom,color=color,label=label);bottom+=ys
        ax.set_title(s);ax.set_ylabel('Mean time per job (s)');ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    handles,legendlabels=axes.flat[0].get_legend_handles_labels();fig.legend(handles,legendlabels,loc='lower center',bbox_to_anchor=(.5,.01),ncol=3,frameon=False)
    fig.suptitle('JCT accounting: training + actual recovery + waiting',fontsize=15)
    for ext in ('png','pdf'):fig.savefig(figs/f'time_decomposition.{ext}',dpi=180)
    plt.close(fig)
    lines=['# CAPRA v2：六个优化机会场景的受控实验结果','',
       '本轮只改变输入场景及其运行/审计接口，保持v2调度策略字节不变。基础提交 `0b87934ae558960921889b01d14502155fb0c41c`；新版本 `CAPRA_V2_SCENARIOS_R1`；本地分支 `capra/scenarios-r1`。原v1/v2成果保留，无远端推送。',
       '',f"正式格完成：{sum(r['status']=='ALL_COMPLETE' for r in results)}/18；完成作业：{sum(r.get('completed') or 0 for r in results)}/1440。每格状态、删失和错误均保留在results.csv/json。只有完整80/80才报告全体JCT分位数。",'',
       '## 原v2六格参考（不是新矩阵的一部分）','',
       '|原负载|方法|mean|P95|P99|','|---|---|---:|---:|---:|']
    for r in old:lines.append('|'+ '|'.join([r['workload'],r['method'],fmt(r['mean_jct']),fmt(r['p95_jct']),fmt(r['p99_jct'])])+'|')
    lines+=['','原六格通过复制件独立原始审计；原结果目录不写回。W2原CAPRA对SIA-P的P95/P99增加约5.70%/9.37%，仍然保留。原RAM比例以上饱和、BERT训练份额低和DS比例已饱和形成了本轮研究动机，不是新实验必胜目标。','',
       '## 新六场景十八格','',
       '时间单位为模拟秒。改善率=100×(1−method/baseline)，正数表示更快；比较仅限同场景同版本。','',
       '|场景|方法|完成/状态|mean|P50|P95|P99|makespan|','|---|---|---|---:|---:|---:|---:|---:|']
    for r in results:lines.append('|'+ '|'.join([r['scenario'],r['method'],f"{r.get('completed')}/80 {r['status']}"]+[fmt(r.get(k)) for k in ('mean_jct','p50_jct','p95_jct','p99_jct','makespan')])+'|')
    lines+=['','|场景|比较|mean改善%|P95改善%|P99改善%|恢复改善%|','|---|---|---:|---:|---:|---:|']
    for c in comparisons:lines.append('|'+ '|'.join([c['scenario'],c['method']+'/'+c['baseline']]+[fmt(c[k+'_improvement_percent']) for k in ('mean_jct','p95_jct','p99_jct','mean_recovery')])+'|')
    lines+=['','![Mean JCT](../runs/scenarios_r1/CAPRA_V2_SCENARIOS_R1/figures/mean_jct.png)','',
        '## 时间分解与完整决策开销','',
        '|场景|方法|等待|训练|恢复|决策median|P95|max|格wall|','|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in results:lines.append('|'+ '|'.join([r['scenario'],r['method']]+[fmt(r.get(k),4 if k.startswith('decision') else 2) for k in ('mean_waiting','mean_training','mean_recovery','decision_median','decision_p95','decision_max','wall_seconds')])+'|')
    lines+=['','开销主口径仅非空决策，包括GPU准备/MIP、参考映射、候选/配额、稳定评分、校验及提交。all_rounds另见各analysis_r1/opportunity_metrics.json。控制器wall不计入模拟JCT，真实恢复计入。训练加权指标来自实际训练段。','',
        '![Time accounting](../runs/scenarios_r1/CAPRA_V2_SCENARIOS_R1/figures/time_decomposition.png)','',
        '## 相对比例性能与CPU/RAM条件增益','',
        'rho_prop使用本场景所在节点的比例CPU/RAM。CPU条件差=rho(c,m)−rho(c_prop,m)；RAM条件差=rho(c,m)−rho(c,m_prop)。两者不能相加解释总收益，更不能直接换算动态JCT因果贡献。','',
        '|场景|方法|加权rho|加权rho/rho_prop|超过比例训练%|CPU条件差|CPU正训练%|RAM条件差|RAM正训练%|','|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for m in analyses:
        x=m['training_metrics'];lines.append('|'+ '|'.join([m['scenario'],m['method'],fmt(x['rho'],4),fmt(x['relative'],4),fmt(x['above_prop']*100),fmt(x['cpu_difference'],4),fmt(x['cpu_positive']*100),fmt(x['ram_difference'],4),fmt(x['ram_positive']*100)])+'|')
    lines+=['','CPU6的rho>1不等于优于同场景比例；CPU2的rho=1可能已超过同场景比例。分应用条件增益、训练/GPU时间份额见opportunity_summary.json。占用积分逐节点及按GPU类型写入各analysis_r1/occupancy.csv，包含恢复，不能称硬件忙碌利用率。','',
        '## 布局、恢复与机会限制','',
        '|场景|方法|非空轮|选F/K/R或P|R原始rho高于F轮|R仅成本优势轮|纯节点迁移|aux更新|可用闲置资源机会轮|RAM候选漏点轮|','|---|---|---:|---|---:|---:|---:|---:|---:|---:|']
    for m in analyses:lines.append('|'+ '|'.join([m['scenario'],m['method'],str(m['active_rounds']),str(m['active_selected']),str(m['R_raw_rho_above_F_rounds']),str(m['R_phi_above_F_without_raw_rho_advantage_rounds']),str(m['pure_node_migrations']),str(m['transitions'].get('aux_update',0)),str(m['unlocked_slack_opportunity_rounds']),str(m['ram_candidate_gap_rounds'])])+'|')
    lines+=['','F/K/R可行次数、失败原因、Phi和未扣恢复sum-rho相对F分布、实际迁移和恢复见opportunity_summary.json及逐轮candidate_deltas.csv。R“仅成本优势”严格指Phi高于F但sum-rho不高于F，不代表全程JCT因果。',
        '', '异敏感度共同入选→同类型→两任务GPU和可单节点容纳→F已同机/锁/直接迁移容量阻断的嵌套描述统计，见funnel_rounds及funnel_training_fraction。训练权重是出现该标志轮次内所有实际任务训练秒；并非成对机会独占训练时间，不同标志不可相加。直接迁移诊断固定第三方任务，不穷尽交换布局。',
        '', '## 静态机制证书和动态漏点','',
        '静态4C+2M+2N证书为24CPU/499.98GB，rho=1.53/2.4/1。静态4C+4M候选中无416.68GB点，保留M250GB/rho1；合法连续416.68GB可得1.50004。这两者与动态结果分开，详见development/static_certificates.json。',
        '', '动态证书固定其他任务、GPU计划及位置，只使用决策时已有空闲资源，且标记恢复锁。每个证书独立成立；多个证书可能争用相同空闲资源，禁止累计预测增益。RAM漏点还要求在当前冻结候选RAM集合中没有能用该闲置RAM产生正增益的点。完整证书见每格analysis_r1/slack_certificates.json。','',
        '## CN/CM SIA-P严格控制','',
        f"控制结果：**{control['status']}**。工作负载/集群哈希、共同费用、逐作业完成/等待/训练/恢复/进度，以及逐轮GPU计划、分配、batch、恢复状态与执行分段全部比较；排除墙钟、缓存、路径与场景名。详情cn_cm_siap_control.json。",'',
        '## 复现、冻结及边界','',
        f"冻结{len(manifest['files_sha256'])}文件；算法及上游保护{len(manifest['algorithm_protected_sha256'])}文件，历史与输入保护{len(manifest['protected_sha256'])}文件。源码包frozen_source.zip可直接复原。27项测试、两次20作业/60轮pilot、真实孙进程Job Object清理、原六格复制重放及相对路径重放通过；pilot未完成全体JCT为空，不参与主表。",'',
        f"准备测试开始到矩阵结束的单调时钟用时{load(OUT/'matrix_receipt.json')['elapsed_seconds']/60:.2f}/120分钟；包含准备运行、复核、写盘、进程清理及中间开发等待。格wall总计{sum(r.get('wall_seconds') or 0 for r in results)/60:.2f}分钟，不能把它替代总预算。分析和报告在正式实验后单独进行，不启动新模拟。",'',
        '单格900秒runner/960秒所属进程树/6000轮，Windows Job Object在挂起创建后分配、恢复执行，终止后确认后代为0；不按进程名终止其他项目。每格记录process/termination和原始输入哈希；无参数搜索、无选择性删除正负结果、无现场算法调参。','',
        '在新工作副本根目录运行（输出目录必须不存在）：','',
        '```powershell',
        '.\\.venv\\Scripts\\python.exe -X utf8 -B scripts/build_scenarios_r1.py --check',
        '.\\.venv\\Scripts\\python.exe -X utf8 -B -m unittest discover -s tests -v',
        '.\\.venv\\Scripts\\python.exe -X utf8 -B -m capra.runner_v2 --input data/scenarios_r1/w2_dense.csv --cluster data/scenarios_r1/cluster_cpu3.json --responses data/scenarios_r1/responses_cm.json --scenario-id w2_dense_cm --run-version CAPRA_V2_SCENARIOS_R1_REPRO --method CAPRA --output runs/scenarios_r1/reproduce-new/CAPRA --max-rounds 6000 --wall-limit 900',
        '.\\.venv\\Scripts\\python.exe -X utf8 -B -c "from capra.audit_v2 import audit; print(audit(\'runs/scenarios_r1/reproduce-new/CAPRA\'))"',
        '.\\.venv\\Scripts\\python.exe -X utf8 -B scripts/analyze_scenarios_r1.py',
        '.\\.venv\\Scripts\\python.exe -X utf8 -B scripts/report_scenarios_r1.py',
        '```','',
        '本轮18格由run_scenarios_r1.py在冻结后一次执行，已有results时拒绝覆写/静默续跑。新机器重现实验须恢复源代码包和锁定环境、独立新目录、重新登记预算及冻结，不复用已耗尽的单调时钟截止。输入生成器可不带--check生成，所有已有目标必须字节相同，否则全部拒绝写入。',
        '', '可解释范围：合成CPU/RAM响应和两条原GPU负载的受控仿真，不是实机测量，不是跨大量负载普遍验证。原画像→CN改变多项响应；只有CN→CM是严格RAM单因素对照。有限候选和F/K/R不保证全局rho或JCT最优，尚未区分全部可能布局/配额oracle差距。',
        '', '## 逐项研究结论与剩余问题','', '下述结论在读取全部18格及原始机会证据后补充。']
    (ROOT/'docs/SCENARIOS_R1_RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    from interpret_scenarios_r1 import append_conclusions
    append_conclusions(ROOT,OUT)
    print(json.dumps(dict(status='REPORT_GENERATED',cells=len(results),control=control['status'],comparisons=comparisons),ensure_ascii=False))
if __name__=='__main__':main()
