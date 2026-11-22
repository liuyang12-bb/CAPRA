"""Offline v2 delivery: six-cell table, preserved v1 reference, pairs and figures."""
from pathlib import Path
from datetime import datetime,timezone
import csv,hashlib,json,os,subprocess
ROOT=Path(__file__).resolve().parents[1]
os.environ['MPLCONFIGDIR']=str(ROOT/'.cache/matplotlib')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def csvwrite(p,rows):
    if rows:
        with p.open('w',encoding='utf8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def fmt(x,d=2):return '—' if x is None else f'{x:.{d}f}'

def main():
    manifest=load(ROOT/'configs/experiment_manifest_v2.json');out=ROOT/'runs/capra_v2'/manifest['version'];results=load(out/'results.json')
    assert len(results)==6
    for name,digest in manifest['files_sha256'].items():assert sha(ROOT/name)==digest,('FROZEN_FILE_CHANGED',name)
    for name,digest in manifest['protected_v1']['sha256'].items():assert sha(ROOT/name)==digest,('HISTORY_CHANGED',name)
    complete=[r for r in results if r.get('audit')=='PASS']
    for r in complete:
        for seal in ('output_hashes.json','audit_hashes.json'):
            for name,digest in load(ROOT/r['output']/seal).items():assert sha(ROOT/r['output']/name)==digest
    groups={w:[r for r in results if r['workload']==w] for w in dict.fromkeys(r['workload'] for r in results)}
    mainrows=[];timings=[];details=[];comparisons=[];pairs=[];nodes=[]
    for w,rr in groups.items():
        baseline=rr[0].get('mean_jct');fixed=rr[1].get('mean_jct');capra=rr[2].get('mean_jct')
        for r in rr:
            change=None if baseline is None or r.get('mean_jct') is None else (r['mean_jct']/baseline-1)*100
            mainrows.append(f"| {w} | {r['method']}-v2 | {r.get('completed')}/{r['total']} {r['status']} | {fmt(r.get('mean_jct'))} | {fmt(change)}% | {fmt(r.get('p50_jct'))} | {fmt(r.get('p95_jct'))} | {fmt(r.get('p99_jct'))} | {fmt(r.get('makespan'))} |")
            timings.append(f"| {w} | {r['method']} | {fmt(r.get('mean_waiting'))} | {fmt(r.get('mean_training'))} | {fmt(r.get('mean_recovery'))} | {fmt(r.get('decision_median'),4)} | {fmt(r.get('decision_p95'),4)} | {fmt(r.get('decision_max'),4)} | {fmt(r.get('wall_seconds'))} |")
            if r.get('audit')=='PASS':
                details.append(dict(workload=w,method=r['method'],selected=r['candidate_selected'],feasible=r['candidate_feasible'],failures=r['candidate_failures'],relative_to_F=r['relative_to_F'],migrations=r['transitions'].get('migration',0),pure_node_migrations=r['pure_node_migrations'],aux_only=r['transitions'].get('aux_update',0),actual_recovery=r['total_actual_recovery'],new_recovery=r['total_new_recovery_cost'],weighted_rho=r['training_weighted_rho'],boosted_training_fraction=r['boosted_training_fraction'],app_train_share=r['application_training_share'],allocated_resource_fraction=r['allocated_resource_fraction'],pairs=r['quota_generated_pairs'],upgrades=r['quota_upgrade_steps'],node_cache_hits=r['node_trial_cache_hits']))
                for nid,a in r['average_node_allocations'].items():nodes.append(dict(workload=w,method=r['method'],node=nid,**a))
        if baseline is not None and fixed is not None and capra is not None:
            comparisons.append(f"- {w}：CAPRA-v2相对SIA-P-v2平均JCT变化{(capra/baseline-1)*100:+.2f}%，相对Fixed-v2变化{(capra/fixed-1)*100:+.2f}%；Fixed-v2相对SIA-P-v2变化{(fixed/baseline-1)*100:+.2f}%。")
            tables={r['method']:{p['job']:p for p in csv.DictReader((ROOT/r['output']/'per_job.csv').open(encoding='utf8',newline=''))} for r in rr}
            for name,b in tables['SIA-P'].items():
                row=dict(workload=w,job=name,application=b['application'],arrival=float(b['arrival']))
                for method in ('SIA-P','CAPRA-Fixed','CAPRA'):
                    assert tables[method][name]['arrival']==b['arrival']
                    for col in ('jct','waiting','training','recovery'):row[method+'_'+col]=float(tables[method][name][col])
                row['CAPRA_minus_SIA_P']=row['CAPRA_jct']-row['SIA-P_jct'];row['CAPRA_minus_Fixed']=row['CAPRA_jct']-row['CAPRA-Fixed_jct'];pairs.append(row)
    csvwrite(out/'paired_jobs.csv',pairs);csvwrite(out/'average_node_allocations.csv',nodes)
    (out/'supplementary_metrics.json').write_text(json.dumps(details,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    old=load(ROOT/'runs/main_v1/results.json')
    csvwrite(out/'v1_historical_reference.csv',[{k:r[k] for k in ('workload','method','mean_jct','p95_jct','p99_jct','makespan','completed','total')} for r in old])
    figs=out/'figures';figs.mkdir(exist_ok=False)
    methods=['SIA-P','CAPRA-Fixed','CAPRA'];colors=['#65758c','#41968a','#cd7653']
    fig,axs=plt.subplots(1,2,figsize=(12,4.3),layout='constrained')
    for ax,(w,rr) in zip(axs,groups.items()):
        values=[r.get('mean_jct',None) for r in rr]
        bars=ax.bar(methods,[v if v is not None else np.nan for v in values],color=colors)
        ax.bar_label(bars,labels=[fmt(v) for v in values],padding=4,fontsize=10)
        ax.set_title(w+' (v2)');ax.set_ylabel('Mean JCT (simulated seconds)');ax.set_ylim(0,max([v for v in values if v is not None] or [1])*1.2)
    fig.savefig(figs/'v2_mean_jct.png',dpi=180);fig.savefig(figs/'v2_mean_jct.pdf');plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(12,4.3),layout='constrained')
    for ax,(w,rr) in zip(axs,groups.items()):
        bottom=np.zeros(3)
        for col,label,color in [('mean_waiting','Waiting','#b5bdc9'),('mean_training','Training','#41968a'),('mean_recovery','Recovery','#cd7653')]:
            values=np.array([r.get(col,0) or 0 for r in rr]);ax.bar(methods,values,bottom=bottom,label=label,color=color);bottom+=values
        ax.set_title(w+' (v2)');ax.set_ylabel('Mean observed time (seconds)');ax.legend(fontsize=9)
    fig.savefig(figs/'v2_time_decomposition.png',dpi=180);fig.savefig(figs/'v2_time_decomposition.pdf');plt.close(fig)
    budget=load(ROOT/'runs/capra_v2/budget_ledger.json')
    stats=[]
    for x in details:
        stats.append(f"| {x['workload']} | {x['method']} | {x['selected']} | {x['feasible']} | {x['migrations']}/{x['pure_node_migrations']} | {x['aux_only']} | {x['actual_recovery']:.1f} | {fmt(x['weighted_rho'],3)} | {fmt(100*x['boosted_training_fraction'])}% |")
    actual=[]
    for w,rr in groups.items():
        if all(r.get('audit')=='PASS' for r in rr):
            f,c=rr[1],rr[2]
            actual.append(f"- {w}，CAPRA减Fixed：平均等待{c['mean_waiting']-f['mean_waiting']:+.2f}秒，训练{c['mean_training']-f['mean_training']:+.2f}秒，恢复{c['mean_recovery']-f['mean_recovery']:+.2f}秒。CAPRA选择{c['candidate_selected']}，F相对收益P95={fmt(c['relative_to_F']['p95'],4)}。")
    text=f'''# CAPRA v2 结果与交付

项目：`{ROOT}`；分支`capra/v2-20261122`；冻结版本`{manifest['version']}`，运行代码提交`{manifest['code_commit']}`。本轮没有远端推送；v1的99个保护文件、原两条80作业CSV、集群和响应表最终哈希保持一致。

22项原有/新增测试最终通过。新增跨设备fixture曾缺少AWS性能字典，修正fixture后通过；保留失败日志`development/tests_final.log`与通过日志`tests_final_02.log`，没有因此重跑正式格。12作业/80轮pilot37秒、原始审计通过，未完成整体JCT留空；仅用于正确性/耗时检查，不加入主表。

## v2 同版本主表

JCT与分位数单位为模拟秒。完整80/80才报告整体统计；负变化表示更快。H=180仅评分，周期仍60秒；控制器wall不扣模拟JCT，真实恢复照常收费。

| 负载 | 方法 | 完成/状态 | mean | 相对SIA-P-v2 | P50 | P95 | P99 | makespan |
|---|---|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(mainrows)}

{chr(10).join(comparisons)}

## 时间分解与完整开销

| 负载 | 方法 | 等待 | 训练 | 恢复 | 决策中位/秒 | P95/秒 | max/秒 | 整格wall/秒 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(timings)}

平均节点GPU/CPU/RAM配额见`average_node_allocations.csv`；各格summary包含集群分配占比和节点均值，含恢复占用，不等于硬件忙碌率。各应用训练时间占比见`supplementary_metrics.json`。完整计时包括GPU信息准备、MIP、参考映射、候选、配额生成/缓存、稳定评分、验证和提交；初始化、导入及审核计入整格wall。

| 负载 | 方法 | 被选次数 | 可行次数 | 迁移/纯节点 | aux-only | 实耗恢复总秒 | 训练加权rho | rho>1训练占比 |
|---|---|---|---|---:|---:|---:|---:|---:|
{chr(10).join(stats)}

失败原因、F/K/R可行次数、Phi相对F分布、有限候选数/升级步数和缓存统计保留在每格summary及原始日志，未用平均值掩盖失败。

## 修复证据与解释范围

- 共享成本：实际应用成本CIFAR50/DeepSpeech25/BERT120；Sia-v2预测、映射、评分与执行一致。原始pilot能直接看到`restart penalty: 50.0`，每个主事件由独立审计再次对照应用源码。
- 节点身份稳定：只比较等价节点identity/swap，用真实费用，锁冲突拒绝、平局规范化幂等。共同参考与F再次处理不变；真实节点变化实际收费。
- 配额遗漏：冻结表fixtures证明1GPU CIFAR3→6CPU的rho=1.75，4GPU CIFAR12→18CPU的rho=1.415；两项BERT3→1CPU释放资源；耦合回收不拼未验证点，联合增配不漏掉共同CPU/RAM收益。
- 布局与选择：资源互补fixture能构造两侧BERT+CIFAR，8+2+2通过GPU-DP防碎片；仅F/K/R，F等于同状态Shared Fixed，失败候选整格丢弃、保留已求F；选中Phi不低于F。
- 执行与审计：输入current来自真实提交，锁剩余不重新收费；原始/锁修复/稳定参考分开记录。独立原始重放核对完整集合、GPU/batch、节点容量、rho一次、转换成本、先恢复后训练、完成与JCT恒等式。

上述机制fixtures是静态验证，不声称原主轨迹都发生。Phi是同状态/同模型的180秒启发式分数；全程GPU和batch轨迹会分化，不保证JCT，也不把逐轮预测节费相加当成两次运行的JCT差。

{chr(10).join(actual)}

若主表收益有限，候选选择次数与相对F收益分布可衡量本模型是否常有布局机会；训练加权rho和boosted比例显示辅助增配实际生效程度；实耗恢复分解显示是否抵消训练收益。有限候选和贪心配额并非全局最优，单凭本六格不能证明布局空间不足或模型外真实性；没有固定状态精确参考的部分仍未确定。

## v1 历史与未覆盖范围

`v1_historical_reference.csv`单列旧结果（负载2：1141.6625/1048.425/1125.6125；负载6：1125.4625/1144.8375/1109.7），不代替v2同版本基线。共同节点稳定与成本修正本身会改变后续GPU轨迹，不能将跨版本差异全部算成新配额或R布局贡献。本轮未预登记额外消融，因此不加跑。

两条负载分别68/67个CIFAR，BERT仅3/5个，未包含Imagenet；原RAM响应在比例以上大体饱和。尚未验证RAM高于比例仍持续获益、多类强CPU/RAM互补、跨设备/batch敏感性真实变化、多节点和真实硬件。仅建议下一轮围绕实际证据挑选问题，不自动改输入或扩矩阵。

## 复现与结束状态

实验计费（pilot+六格及失败）{budget['used_seconds']/60:.2f}分钟；另保守预留60秒机制验证，预算占用{budget['accounted_seconds']/60:.2f}/120分钟。未静默延长单格900秒/进程960秒/6000轮限制。完整实验journal为`runs/capra_v2/budget_ledger.json`。

冻结清单`configs/experiment_manifest_v2.json`、精确运行源码`runs/capra_v2/{manifest['version']}/frozen_source.zip`，代码与输入hash在冻结/最终核对文件中。所有原始事件、逐作业、资源、终止、审核和hash均位于六格目录。原始正负逐任务差异见`paired_jobs.csv`；无显著性声明、无H搜索、无自动重复种子、无远端推送。

在CAPRA根目录，用专属环境执行：

```powershell
.\\.venv\\Scripts\\python.exe -X utf8 -B -m unittest discover -s tests -v
.\\.venv\\Scripts\\python.exe -X utf8 -B -m capra.runner_v2 --input data/saturn-2-supported80.csv --method CAPRA --output runs/capra_v2/reproduce-new/CAPRA --wall-limit 900 --max-rounds 6000
```

输出目录必须不存在；严格冻结六格由`scripts/run_v2.py`执行，已有本轮目录不可原地重跑。安装依赖使用独立`requirements_v2.lock.txt`；数值核心仍保持v1固定版本。Matplotlib3.9.4仅用于本报告PNG/PDF，不参与调度。

本轮到此结束。下一步先解释同版本表中的训练/恢复和候选收益证据，再决定研究方向；不以需要获胜为由扩大搜索、改表或追加实验。
'''
    (ROOT/'docs/CAPRA_V2_RESULTS.md').write_text(text,encoding='utf8')
    receipt=dict(status='PASS',version=manifest['version'],code_commit=manifest['code_commit'],frozen_files=len(manifest['files_sha256']),source_unchanged=True,v1_protected_files=len(manifest['protected_v1']['sha256']),v1_unchanged=True,
        cells=6,complete=sum(r['status']=='ALL_COMPLETE' for r in results),audited=len(complete),paired_jobs=len(pairs),budget=budget,remote_push=False)
    (out/'final_verification.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8')
    hashes={str(p.relative_to(ROOT)):sha(p) for p in out.rglob('*') if p.is_file() and p.name!='evidence_hashes.json'}
    hashes['docs/CAPRA_V2_RESULTS.md']=sha(ROOT/'docs/CAPRA_V2_RESULTS.md')
    (out/'evidence_hashes.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(report=str(ROOT/'docs/CAPRA_V2_RESULTS.md'),figures=str(figs),**receipt),ensure_ascii=False))

if __name__=='__main__':main()
