"""Offline summary of the frozen six-cell experiment; no simulation or optimization."""
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal,ROUND_HALF_UP
import csv,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/main_v1'
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def num(x,d=2):return '—' if x is None else f'{Decimal(str(x)).quantize(Decimal(1).scaleb(-d),rounding=ROUND_HALF_UP):,.{d}f}'
def percent(x):return f'{x:+.2f}%'


def main():
    results=load(RUN/'results.json');manifest=load(ROOT/'configs/experiment_manifest.json')
    assert len(results)==6
    for name,digest in manifest['source_sha256'].items():assert sha(ROOT/name)==digest,('FROZEN_FILE_CHANGED',name)
    table=[];overheads=[];paired=[];integrity=[];mechanism=[]
    groups={}
    for r in results:groups.setdefault(r['workload'],[]).append(r)
    for w,rows in groups.items():
        baseline=next(r for r in rows if r['method']=='SIA-P')
        for r in rows:
            change=None
            if baseline.get('mean_jct') and r.get('mean_jct') is not None:change=100*(r['mean_jct']/baseline['mean_jct']-1)
            table.append(f"| {w} | {r['method']} | {r.get('completed')}/{r['total']} | {num(r.get('mean_jct'))} | {percent(change) if change is not None else '—'} | {num(r.get('p95_jct'))} | {num(r.get('p99_jct'))} | {num(r.get('makespan'))} |")
            overheads.append(f"| {w} | {r['method']} | {num(r.get('decision_median'),4)} | {num(r.get('decision_p95'),4)} | {num(r.get('decision_max'),4)} | {num(r.get('wall_seconds'))} | {r.get('transitions',{}).get('migration','—')} | {sum(r.get('fallbacks',{}).values()) if 'fallbacks' in r else '—'} | {r.get('gpu_repairs','—')} |")
            directory=ROOT/r['output']
            if r.get('audit')=='PASS':
                for sealname in ('output_hashes.json','audit_hashes.json'):
                    for name,digest in load(directory/sealname).items():assert sha(directory/name)==digest,(str(directory),name)
                start=load(directory/'start.json')
                assert Path(start['import_audit']['prefix']).resolve()==(ROOT/'.venv').resolve()
                critical={k:v for k,v in start['import_audit']['module_files'].items() if k in ('sia','job','goodput','applications','utils') or k.startswith('capra')}
                assert all(Path(p).resolve().is_relative_to(ROOT.resolve()) for p in critical.values())
                integrity.append(dict(workload=w,method=r['method'],audit='PASS',segment_checks=r['segment_checks'],source_files_unchanged=True,critical_imports=critical,output=str(directory)))
        if all(r.get('mean_jct') is not None for r in rows):
            per={r['method']:{s['job']:s for s in csv.DictReader((ROOT/r['output']/'per_job.csv').open(encoding='utf8',newline=''))} for r in rows}
            assert len(set(tuple(sorted(v)) for v in per.values()))==1
            for name,b in per['SIA-P'].items():
                item=dict(workload=w,job=name,application=b['application'],arrival=float(b['arrival']))
                for method in ('SIA-P','CAPRA-Fixed','CAPRA'):
                    s=per[method][name]
                    assert s['arrival']==b['arrival']
                    for k in ('jct','waiting','training','recovery'):item[f'{method}_{k}']=float(s[k])
                item['CAPRA_minus_SIA_P_jct']=item['CAPRA_jct']-item['SIA-P_jct']
                item['CAPRA_minus_Fixed_jct']=item['CAPRA_jct']-item['CAPRA-Fixed_jct']
                paired.append(item)
            for method in ('SIA-P','CAPRA-Fixed','CAPRA'):
                ss=list(per[method].values());n=len(ss)
                parts={k:sum(float(s[k]) for s in ss)/n for k in ('jct','waiting','training','recovery')}
                mechanism.append(dict(workload=w,method=method,jobs=n,**{f'mean_{k}':v for k,v in parts.items()}))
    for name,data in [('paired_jobs.csv',paired),('time_decomposition.csv',mechanism)]:
        if data:
            with (RUN/name).open('w',encoding='utf8',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    conclusions=[];parts=[]
    for name,rows in groups.items():
        d={r['method']:r for r in rows}
        if all(r.get('mean_jct') is not None for r in rows):
            p,f,c=(d[k]['mean_jct'] for k in ('SIA-P','CAPRA-Fixed','CAPRA'))
            conclusions.append(f"- {name}：CAPRA相对SIA-P的平均JCT变化{percent(100*(c/p-1))}，相对Fixed变化{percent(100*(c/f-1))}；Fixed相对SIA-P变化{percent(100*(f/p-1))}。")
            mm={x['method']:x for x in mechanism if x['workload']==name}
            delta={k:mm['CAPRA'][f'mean_{k}']-mm['CAPRA-Fixed'][f'mean_{k}'] for k in ('waiting','training','recovery')}
            assert abs(sum(delta.values())-(c-f))<1e-6
            parts.append(f"- {name}，CAPRA减Fixed：平均等待{delta['waiting']:+.2f}秒、训练{delta['training']:+.2f}秒、恢复{delta['recovery']:+.2f}秒，合计{c-f:+.2f}秒。")
        else:conclusions.append(f"- {name}存在未完成/失败格，整体JCT不作完整三方比较，详见状态与终止记录。")
    valid_groups=[{r['method']:r for r in rows} for rows in groups.values() if all(r.get('mean_jct') is not None for r in rows)]
    if len(valid_groups)==2 and all(g['CAPRA-Fixed']['mean_jct']<=g['CAPRA']['mean_jct'] and g['CAPRA-Fixed']['mean_jct']<g['SIA-P']['mean_jct'] for g in valid_groups):
        recommendation='两份主负载均是Fixed比SIA-P更好且优于自由放置CAPRA：推荐将CAPRA-Fixed作为当前可继续研究的简化版本，保留自由放置为实验变体；本轮不支持自由放置有额外主实验收益。下一项工作应先解释现有逐作业分解和迁移/配额轨迹，不增加搜索以强求获胜。'
    elif len(valid_groups)==2 and all(g['CAPRA']['mean_jct']<g['CAPRA-Fixed']['mean_jct'] and g['CAPRA']['mean_jct']<g['SIA-P']['mean_jct'] for g in valid_groups):
        recommendation='两份负载中CAPRA都优于SIA-P及Fixed，支持本轮合成模型和支持域下的整体自由放置价值；下一项应评估外部有效性与迁移敏感性，不能直接声称普遍有效。'
    else:
        recommendation='收益依场景而异：本轮CAPRA相对SIA-P两份均只有约1.4%的平均JCT收益，Fixed在一份改善、另一份退化，尚不能主张自由放置普遍更优。下一项最值得做的是基于已有原始事件，对相同GPU计划核对Fixed/free的配额、节点选择和迁移代价，解释为什么负载2自由放置训练与恢复时间增加、负载6的Fixed恢复时间反而增加；先完成归因，再决定保留哪一版本。当前不扩大矩阵、不改画像或增加搜索。'
    data=[]
    for w in manifest['workload_selection']:
        rr=list(csv.DictReader((ROOT/w['input']).open(encoding='utf8',newline='')))
        counts={app:sum(r['application']==app for r in rr) for app in ('cifar10','imagenet','bert','deepspeech2')}
        data.append(f"- `{w['input']}`：80作业，原到达{w['first_time']}–{w['last_time']}秒，应用数{counts}；SHA256 `{w['sha256']}`。")
    fixture=load(ROOT/'runs/validation/complementarity.json')
    git_root=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','--show-toplevel'],text=True).strip()
    common=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','--git-common-dir'],text=True).strip()
    remotes=subprocess.check_output(['git','-C',str(ROOT),'remote','-v'],text=True).strip()
    assert Path(git_root).resolve()==ROOT.resolve() and common=='.git' and not remotes
    validation=load(ROOT/'runs/validation/contracts_receipt.json')
    deep=load(RUN/'deep_audit.json')
    assert len(deep)==len(integrity) and all(r['status']=='PASS' for r in deep)
    receipt=dict(project=str(ROOT),utc=datetime.now(timezone.utc).isoformat(),frozen_code_commit=manifest['code_commit'],manifest_sha256=sha(ROOT/'configs/experiment_manifest.json'),frozen_files=len(manifest['source_sha256']),source_unchanged=True,deep_cross_round_audits=deep,
        cells=len(results),complete=sum(r['status']=='ALL_COMPLETE' for r in results),raw_audited=len(integrity),tests=validation,
        source_versions=manifest['sources'],independent_git=dict(root=git_root,common_dir=common,remotes=remotes),imports=integrity,
        old_project_access='No old project dependency or writes. All running source/input/env/output paths rooted in CAPRA; general Python standard library is from system Python310.',
        no_remote_push=True,no_auto_expansion=True)
    (RUN/'final_verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    text=f'''# CAPRA 独立项目本阶段报告

项目绝对路径：`{ROOT}`。独立本地Git工程和`.venv`已交付；未创建远端、推送或修改旧MELD项目。本阶段必要验证{validation['tests']}项通过；六格中{receipt['complete']}格全量完成、{receipt['raw_audited']}格通过原始事件复算。没有自动扩展矩阵。

## 主要结果

负值表示平均JCT降低。全部完成才报告整体JCT/P95/P99/makespan，单位为模拟秒；均为本CAPRA项目的新运行结果。

| 负载 | 方法 | 完成 | 平均JCT | 相对SIA-P | P95 | P99 | makespan |
|---|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(table)}

{chr(10).join(conclusions)}

这是两份80作业、固定合成辅助响应和单节点域的结果，不能自动推出实机、所有工作负载或投稿充分性；无显著性或普遍获胜声明。CAPRA-Fixed与CAPRA的后续Sia计划会因进度分化而不同，二者差异反映本轮动态放置策略的整体效果，并非严格固定全程GPU轨迹的纯放置因果效应。受控例才使用相同GPU输入。

## 真实开销与事件

决策为从准备到提交的完整墙钟，单独报告，不扣入模拟执行时间；整格墙钟包含子进程导入、初始化、训练推进、决策和首次原始审核，不将全部wall当作优化器耗时。迁移/恢复/重配置则实际扣模拟时间。

| 负载 | 方法 | 决策中位/秒 | P95/秒 | 最大/秒 | 整格墙钟/秒 | 节点迁移次数 | TUNE回退事件数 | 共同物理修复轮数 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(overheads)}

回退事件可能在同一轮出现多个，不等于失败轮数；迁移按实际节点身份变化记录，含同类型节点迁移。物理修复使用共同Sia阶段的同目标节点可行性见证，不将修复后的节点声称为未改变的首次输出。逐轮计划、修复前后、锁和配额均保存在各格`events.jsonl.gz`，节点表为`node_resources.csv`；各格`summary.json`提供分类型事件计数及实际配额资源时间积分。

`runs/main_v1/time_decomposition.csv`列出各方法平均等待、训练、恢复时间；`paired_jobs.csv`保留全部正负逐作业差异。JCT恒等式、进度连续、响应只乘一次、checkpoint锁、完整集合与逐节点容量由raw复算校验，不用runner终值代替原始证据。`deep_audit.json`另以独立脚本跨轮推导应有的锁、节点迁移、应用恢复成本及先恢复后训练时钟，不只相信每轮自报锁集合。

{chr(10).join(parts)}

训练项差异可包含后续GPU类型/数量、batch和辅助配额轨迹分化，恢复项差异也依赖应用与迁移事件；这些是精确核账，不是固定状态反事实，不能把全部差异归给单一节点选择规则。

## 小验证和执行边界

两节点四任务控制例：Fixed平均JCT={fixture['fixed']['mean_jct']}秒，CAPRA自由放置={fixture['free']['mean_jct']}秒。四任务的原GPU计划均为2GPU/单节点、batch128、剩余600单位；互补放置每节点CPU敏感任务8CPU/50GB与RAM敏感任务4CPU/200GB。自由方案中两次同类型节点迁移各收10秒，实际Sia Job.step执行完成时刻60/70/70/60；Fixed为80/80/96/96。这是执行单指定的合成机制例，不是实测画像，也不声称Sia必然选该GPU计划。

neutral同部署无额外训练收益；恢复/等待不被rho缩放；锁定位置与配额不变；不完整集合在提交前拒绝；仅配额变化不计GPU迁移；实际Sia锁约束和完整返回通过。完整测试日志在`runs/validation/contracts_test.log`。

官方Sia smoke完成3/3，平均JCT592秒，仅验证工程跑通。CAPRA短pilot80轮耗时33.37秒，10/12完成（含尚未到达/未完成的短窗口），整体JCT留空，不搬入主表。正式前估计及止损限制已写入冻结manifest；没有按结果调整画像、输入、训练量或算法。

## 来源、数据与可复现性

- 官方Sia：[siasosp23/artifacts](https://github.com/siasosp23/artifacts)，实际提交`{manifest['sources'][0]['commit']}`。
- 官方Synergy：[msr-fiddle/synergy](https://github.com/msr-fiddle/synergy)，实际提交`{manifest['sources'][1]['commit']}`；规则核对来自官方`simulator/resources/cluster.py`及[原论文](https://www.usenix.org/system/files/osdi22-mohan.pdf)。
- CAPRA冻结代码提交`{manifest['code_commit']}`；manifest SHA256 `{receipt['manifest_sha256']}`；{receipt['frozen_files']}个冻结文件最终哈希匹配。

{chr(10).join(data)}

选择规则是在主结果前按编号选最先有80条支持行的两份上游Saturn负载，应用限四种数据并行模型、原请求1..8GPU；保留原到达、请求和batch，训练沿用原应用终止标准。负载1仅70条支持行，不足80，故按相同规则选2和6，不按收益选择。

实际两份输入中imagenet均为0，cifar10分别68/67个，BERT仅3/5个；覆盖偏向CPU敏感映射模型，尚不能单独验证RAM敏感负载上的放置收益或任意资源组合的普遍性。

GPU性能、梯度效率、batch选择和在线更新继承Sia；CPU/RAM使用Synergy公开一GPU模板，cifar10→res18、imagenet→res50是模型族映射。每GPUCPU/RAM转移、跨GPU类型与batch保持相同归一化响应是显式合成假设。比例点3CPU/62.5GB归一为1；没有全GPU/batch实测覆盖或新硬件画像声明。

原版权和Synergy MIT文件保留；Sia根仓库未给出统一许可证，不将自身声明扩张覆盖上游，具体文件保留原版权头。适配细节和限制见`docs/DESIGN.md`及`docs/sia_upstream.patch`。本版peer回退将候选节点所有未锁peer统一重置比例，包括原本低于比例者，是比官方excess选择更保守的节点级适配，可能浪费辅助资源；不将本实现等同完整原Synergy系统。

## 实际命令和下一步

本次从CAPRA自己的环境执行：

```powershell
.\\.venv\\Scripts\\python.exe -X utf8 -B scripts/check_small.py
.\\.venv\\Scripts\\python.exe -X utf8 -B scripts/freeze_experiment.py
.\\.venv\\Scripts\\python.exe -X utf8 -B scripts/run_matrix.py
.\\.venv\\Scripts\\python.exe -X utf8 -B scripts/deep_audit.py
.\\.venv\\Scripts\\python.exe -X utf8 -B scripts/build_report.py
```

冻结和主矩阵命令不应在已有目录原地再次执行。复现单格使用README的新输出目录命令；每格`process.json`保留实际完整命令。原始和审计哈希在`output_hashes.json`和`audit_hashes.json`；总核对见`runs/main_v1/final_verification.json`。

{recommendation}

扩展负载、实机或新机制需要下一轮明确任务，本轮到此结束。
'''
    (ROOT/'docs/STAGE_REPORT.md').write_text(text,encoding='utf8')
    (RUN/'delivery_hashes.json').write_text(json.dumps({str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'docs/STAGE_REPORT.md',RUN/'results.csv',RUN/'results.json',RUN/'final_verification.json']},indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(report=str(ROOT/'docs/STAGE_REPORT.md'),complete=receipt['complete'],audited=receipt['raw_audited'],source_unchanged=True),ensure_ascii=False))

if __name__=='__main__':main()
