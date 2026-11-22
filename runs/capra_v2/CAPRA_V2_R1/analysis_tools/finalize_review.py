"""Finalize already completed evidence and figure layout, never run simulations."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,shutil,time
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parents[1]
os.environ['MPLCONFIGDIR']=str(ROOT/'.cache/matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=load(ROOT/'configs/experiment_manifest_v2.json');rows=load(OUT/'results.json');raw=load(OUT/'raw_opportunity_analysis.json')
for n,h in m['files_sha256'].items():assert sha(ROOT/n)==h,('RUNTIME_CHANGED',n)
for n,h in m['protected_v1']['sha256'].items():assert sha(ROOT/n)==h,('HISTORY_CHANGED',n)
assert len(rows)==6 and all(r['status']=='ALL_COMPLETE' and r['completed']==80 and r['v2_raw_audit']=='PASS' for r in rows)
report=ROOT/'docs/CAPRA_V2_RESULTS.md';revisions=OUT/'report_revisions';revisions.mkdir(exist_ok=False)
shutil.copy2(report,revisions/'initial_generated_report.md')
figures=OUT/'figures'
for suffix in ('png','pdf'):shutil.copy2(figures/f'v2_time_decomposition.{suffix}',revisions/f'initial_time_decomposition.{suffix}')
groups={w:[r for r in rows if r['workload']==w] for w in dict.fromkeys(r['workload'] for r in rows)}
fig,axes=plt.subplots(1,2,figsize=(12,4.8))
for ax,(w,rr) in zip(axes,groups.items()):
    bottom=np.zeros(3)
    for field,label,color in [('mean_waiting','Waiting','#b5bdc9'),('mean_training','Training','#41968a'),('mean_recovery','Recovery','#cd7653')]:
        values=np.array([r[field] for r in rr]);ax.bar(['SIA-P','CAPRA-Fixed','CAPRA'],values,bottom=bottom,label=label,color=color);bottom+=values
    ax.set_title(w+' (v2)',fontsize=12);ax.set_ylabel('Mean observed time (seconds)');ax.set_ylim(0,max(bottom)*1.1)
handles,labels=axes[0].get_legend_handles_labels()
fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.5,1.0),ncol=3,frameon=False)
fig.tight_layout(rect=(0,0,1,.90))
for suffix in ('png','pdf'):fig.savefig(figures/f'v2_time_decomposition.{suffix}',dpi=180)
plt.close(fig)

append=['\n## 原始事件补充复核与实际结论\n',
'以下统计仅重读既有日志，不重新计算布局、不启动模拟；复现脚本为本运行目录`analysis_tools/supplement_v2.py`，数据为`raw_opportunity_analysis.json`及`application_time_and_jct.csv`。主表候选次数含空队列轮次，下表只统计非空决策。\n',
'| 负载 | 非空决策 | 选择F/K/R | K高于F | R高于F | 中间CPU训练区间 | BERT回收训练区间 | CIFAR整节点训练占比 |\n|---|---:|---|---:|---:|---:|---:|---:|']
for x in raw:
    if x['method']=='CAPRA':
        s=x['selected_active'];p=x['positive_phi_over_F_active'];c=x['counters']
        append.append(f"| {x['workload']} | {x['active_decisions']} | {s.get('F',0)}/{s.get('K',0)}/{s.get('R',0)} | {p.get('K',0)} | {p.get('R',0)} | {c.get('intermediate_cpu_training_intervals',0)} | {c.get('bert_reclaimed_training_intervals',0)} | {x['cifar_full_node_training_fraction']*100:.2f}% |")
append.extend(['\n直接的执行证据：负载2的round83，`cifar10-24`使用2GPU/15CPU/125GB，rho=2.075，实际训练60秒；负载6的round19，`cifar10-2`使用4GPU/21CPU/250GB，rho=1.585，实际训练60秒。它们不是旧CPU轴乘GPU数能够表达的点。BERT示例分别为round51的`bert-15`、round91的`bert-22`，均1GPU/1CPU/20.83GB且rho=1，实际训练60秒。详见JSON里的原始轮次与任务ID；区间计数不等于独立作业样本数。\n',
'**归因边界。** 配额升级确已在主实验生效，CAPRA训练时间加权rho为1.150/1.213，rho>1的训练时间占15.36%/23.98%；不能说CPU维度没有作用。额外布局机会在本三候选中有限：R只在23/29个非空轮次模型分数高于F、最终各采用7次，而K采用39/35次。该证据支持本轮多数额外收益与减少恢复相关，但不能证明更广布局或配额精确解没有收益；本轮没有全局oracle与新增消融，贪心配额局限和三布局搜索局限尚未分离。\n',
'“CIFAR单任务占满节点导致大部分辅助收益受限”的解释未被本数据支持：CAPRA中这种训练仅占CIFAR训练时间2.35%/3.42%，不能当作主要慢因。其他配额机会受同机资源、同版本Sia计划及响应模型约束，单靠空闲容量也不能推断存在可行的全面加速。\n',
'**尾部明确保留。** 负载2的CAPRA相对SIA-P-v2，P95增加5.70%、P99增加9.37%；相对Fixed，P95/P99分别增加9.15%/10.58%。其中DeepSpeech2组平均JCT由Fixed的3123.22秒升至3308.89秒，CIFAR组则由685.46降至636.99秒；这是组别结果分化，不是已证明的单条因果链。负载6的CAPRA相对SIA-P，P95增加0.36%、P99约下降0.05%，尾部近似持平；相对Fixed，P99下降9.74%。\n',
'同状态选择中有8/16轮出现个别任务窗口贡献下降，但全体Phi不低于F；另有2/1轮选中方案的未扣费sum-rho低于F。这说明实现允许通过整体收益交换个体短期进度，也说明不应把未扣费rho高低单独当成最终收益。它不能用于把这些轮次与全程JCT差直接等同。\n',
'**推荐下一步。** 优先用当前已有逐作业数据解释负载2的DeepSpeech2尾部及GPU/batch/恢复轨迹分化；再决定是否需要新的受控验证。当前均值已有收益，但没有尾部保证，不以加大H、重选负载或增加搜索来追求全指标获胜。本轮结束，不追加实验。未来尚需验证RAM高于比例仍有收益、强CPU/RAM互补、真实跨GPU/batch敏感性和实机条件。\n',
'离线原始审计可复制命令（拒绝v1输入，使用v2规则）：\n```powershell\n.\\.venv\\Scripts\\python.exe -X utf8 -B scripts/replay_v2_audit.py runs/capra_v2/CAPRA_V2_R1/saturn-2-supported80/CAPRA\n.\\.venv\\Scripts\\python.exe -X utf8 -B runs/capra_v2/CAPRA_V2_R1/analysis_tools/supplement_v2.py\n```\n',
'两个离线汇总工具是在实验结束后添加，不是调度运行文件，不改变冻结的1030项源码或已有运行。图表初稿与报告初稿保留在`report_revisions`；仅将时间分解图图例移到图外，数据不变。\n'])
first=(ROOT/'.git/logs/refs/heads/capra/v2-20261122').read_text(encoding='utf8').splitlines()[0]
epoch=int(first.split('\t')[0].rsplit(' ',2)[-2]);now=time.time();minutes=(now-epoch)/60
append.append(f'本地v2分支创建至本次复盘墙钟约{minutes:.2f}分钟（含实施、验证、实验和图表；首次需求读取/只读核对另计）。模拟实验累计23.56分钟，含机制验证预留的预算计费24.56分钟，低于120分钟上限。\n')
report.write_text(report.read_text(encoding='utf8')+'\n'.join(append),encoding='utf8')
readme=ROOT/'README.md'
readme.write_text(readme.read_text(encoding='utf8')+'''\n## CAPRA v2 本地交付\n\n新版在`capra/v2-20261122`分支，尚未推送。方法见[CAPRA_V2_DESIGN](docs/CAPRA_V2_DESIGN.md)，结果见[CAPRA_V2_RESULTS](docs/CAPRA_V2_RESULTS.md)。运行入口为`python -X utf8 -B -m capra.runner_v2`；依赖锁为`requirements_v2.lock.txt`。六格原始输出位于`runs/capra_v2/CAPRA_V2_R1`，冻结清单为`configs/experiment_manifest_v2.json`。原v1命令/结果与旧manifest保留；不同版本结果不要拼表。\n''',encoding='utf8')
v=load(OUT/'final_verification.json');v.update(task_wall_since_branch_seconds=now-epoch,branch_created_utc=datetime.fromtimestamp(epoch,timezone.utc).isoformat(),review_utc=datetime.now(timezone.utc).isoformat(),postprocessing_only=True,figure_review_status='awaiting_final_png_check',no_additional_simulation=True)
(OUT/'final_verification.json').write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(report=str(report),source_unchanged=True,v1_unchanged=True,elapsed_minutes=minutes,postprocessing_only=True),ensure_ascii=False))
